// zed_oc_depth_recorder.cpp
//
// Records rectified left RGB + SGBM depth from a ZED camera using zed-open-capture.
//
// Calibration is downloaded from Stereolabs on first use (requires wget + internet) and
// cached at ~/zed/settings/SN<serial>.conf.  Subsequent runs work offline.
//
// Output layout matches zed_export_rgbd_trajectory.py (NVIDIA path) so downstream
// tools are interchangeable across CPU and NVIDIA captures:
//
//   <out>/
//   ├── rgb/           NNNNNN.png  (left camera, BGR, rectified)
//   ├── depth_png/     NNNNNN.png  (uint16, millimeters, aligned to left)
//   ├── rgb.txt        (TUM: timestamp rgb/NNNNNN.png)
//   ├── depth.txt      (TUM: timestamp depth_png/NNNNNN.png)
//   ├── calibration.json
//   └── metadata.json
//
// Build inside the container:
//   g++ -std=c++17 -O2 -DVIDEO_MOD_AVAILABLE
//       -I/usr/local/include/zed-open-capture
//       -o /usr/local/bin/zed_oc_depth_recorder
//       zed_oc_depth_recorder.cpp
//       $(pkg-config --cflags --libs opencv4)
//       -lzed_open_capture

#include <opencv2/core.hpp>
#include <opencv2/core/ocl.hpp>
#include <opencv2/calib3d.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/imgcodecs.hpp>

// Must come after OpenCV headers: videocapture.hpp is gated on VIDEO_MOD_AVAILABLE
// (set via -D flag) and uses cv:: types. Including OpenCV first avoids any
// namespace-order issues in downstream sample helper headers.
#include "videocapture.hpp"

#include <chrono>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <getopt.h>
#include <string>
#include <thread>
#include <unordered_map>

namespace fs = std::filesystem;

static volatile sig_atomic_t g_stop = 0;
static void on_signal(int) { g_stop = 1; }

// ---------------------------------------------------------------------------
// Calibration: download + parse .conf file
// ---------------------------------------------------------------------------

static std::string calib_path(int sn) {
    const char* home = getenv("HOME");
    if (!home) home = "/root";
    std::string dir = std::string(home) + "/zed/settings/";
    fs::create_directories(dir);
    return dir + "SN" + std::to_string(sn) + ".conf";
}

static bool download_calib(int sn, const std::string& path) {
    if (fs::exists(path) && fs::file_size(path) > 100)
        return true;
    std::string url = "'https://calib.stereolabs.com/?SN=" + std::to_string(sn) + "'";
    std::string cmd = "wget -q " + url + " -O " + path;
    fprintf(stdout, "Downloading calibration: %s\n", cmd.c_str());
    int ret = system(cmd.c_str());
    return ret == 0 && fs::exists(path) && fs::file_size(path) > 100;
}

// Minimal INI parser: returns map of "section:key" -> value string
static std::unordered_map<std::string, std::string> parse_ini(const std::string& path) {
    std::unordered_map<std::string, std::string> m;
    std::ifstream f(path);
    std::string line, section;
    while (std::getline(f, line)) {
        if (line.empty() || line[0] == ';' || line[0] == '#') continue;
        if (line[0] == '[') {
            auto end = line.find(']');
            if (end != std::string::npos)
                section = line.substr(1, end - 1);
            continue;
        }
        auto eq = line.find('=');
        if (eq == std::string::npos) continue;
        std::string key = line.substr(0, eq);
        std::string val = line.substr(eq + 1);
        // Trim whitespace
        while (!key.empty() && (key.back() == ' ' || key.back() == '\t')) key.pop_back();
        while (!val.empty() && (val.front() == ' ' || val.front() == '\t')) val = val.substr(1);
        m[section + ":" + key] = val;
    }
    return m;
}

static float ini_float(const std::unordered_map<std::string, std::string>& m,
                        const std::string& key, float def = 0.f) {
    auto it = m.find(key);
    if (it == m.end()) return def;
    try { return std::stof(it->second); } catch (...) { return def; }
}

struct CalibResult {
    cv::Mat map_lx, map_ly, map_rx, map_ry;
    cv::Mat cam_l;   // Rectified camera matrix (P1) for left eye
    double  baseline_mm = 0.0;
};

static bool load_calibration(int sn, cv::Size img_size, CalibResult& out) {
    std::string path = calib_path(sn);
    if (!download_calib(sn, path)) {
        fprintf(stderr, "ERROR: Calibration download failed for SN=%d.\n"
                "  Ensure wget can reach https://calib.stereolabs.com\n"
                "  Cached at: %s\n", sn, path.c_str());
        return false;
    }

    auto ini = parse_ini(path);

    // Resolution key suffix
    std::string res;
    switch (img_size.width) {
        case 2208: res = "2k";  break;
        case 1920: res = "fhd"; break;
        case 672:  res = "vga"; break;
        default:   res = "hd";  break;  // 1280 → HD720
    }

    float lfx = ini_float(ini, "LEFT_CAM_" + res + ":fx");
    float lfy = ini_float(ini, "LEFT_CAM_" + res + ":fy");
    float lcx = ini_float(ini, "LEFT_CAM_" + res + ":cx");
    float lcy = ini_float(ini, "LEFT_CAM_" + res + ":cy");
    float lk1 = ini_float(ini, "LEFT_CAM_" + res + ":k1");
    float lk2 = ini_float(ini, "LEFT_CAM_" + res + ":k2");
    float lp1 = ini_float(ini, "LEFT_CAM_" + res + ":p1");
    float lp2 = ini_float(ini, "LEFT_CAM_" + res + ":p2");
    float lk3 = ini_float(ini, "LEFT_CAM_" + res + ":k3");

    float rfx = ini_float(ini, "RIGHT_CAM_" + res + ":fx");
    float rfy = ini_float(ini, "RIGHT_CAM_" + res + ":fy");
    float rcx = ini_float(ini, "RIGHT_CAM_" + res + ":cx");
    float rcy = ini_float(ini, "RIGHT_CAM_" + res + ":cy");
    float rk1 = ini_float(ini, "RIGHT_CAM_" + res + ":k1");
    float rk2 = ini_float(ini, "RIGHT_CAM_" + res + ":k2");
    float rp1 = ini_float(ini, "RIGHT_CAM_" + res + ":p1");
    float rp2 = ini_float(ini, "RIGHT_CAM_" + res + ":p2");
    float rk3 = ini_float(ini, "RIGHT_CAM_" + res + ":k3");

    float baseline = ini_float(ini, "STEREO:baseline");
    float rx       = ini_float(ini, "STEREO:rx_" + res);
    float ry       = ini_float(ini, "STEREO:cv_" + res);  // key is "cv" for the Y component
    float rz       = ini_float(ini, "STEREO:rz_" + res);
    float ty       = ini_float(ini, "STEREO:ty_" + res);
    float tz       = ini_float(ini, "STEREO:tz_" + res);

    if (lfx == 0 || rfx == 0) {
        fprintf(stderr, "ERROR: Calibration file appears empty/invalid for SN=%d res=%s\n"
                "  Try deleting %s and re-running to re-download.\n",
                sn, res.c_str(), path.c_str());
        return false;
    }

    cv::Mat K_l = (cv::Mat_<double>(3, 3) << lfx, 0, lcx, 0, lfy, lcy, 0, 0, 1);
    cv::Mat K_r = (cv::Mat_<double>(3, 3) << rfx, 0, rcx, 0, rfy, rcy, 0, 0, 1);
    cv::Mat D_l = (cv::Mat_<double>(5, 1) << lk1, lk2, lp1, lp2, lk3);
    cv::Mat D_r = (cv::Mat_<double>(5, 1) << rk1, rk2, rp1, rp2, rk3);

    // Rodrigues rotation vector → matrix
    cv::Mat rvec = (cv::Mat_<double>(1, 3) << rx, ry, rz);
    cv::Mat R;
    cv::Rodrigues(rvec, R);

    cv::Mat T = (cv::Mat_<double>(3, 1) << baseline, ty, tz);

    cv::Mat R1, R2, P1, P2, Q;
    cv::stereoRectify(K_l, D_l, K_r, D_r, img_size, R, T,
                      R1, R2, P1, P2, Q, cv::CALIB_ZERO_DISPARITY, 0, img_size);

    cv::initUndistortRectifyMap(K_l, D_l, R1, P1, img_size, CV_32FC1, out.map_lx, out.map_ly);
    cv::initUndistortRectifyMap(K_r, D_r, R2, P2, img_size, CV_32FC1, out.map_rx, out.map_ry);

    out.cam_l        = P1;
    out.baseline_mm  = static_cast<double>(baseline);
    return true;
}

// ---------------------------------------------------------------------------
// Argument parsing helpers
// ---------------------------------------------------------------------------

static void print_usage(const char* prog) {
    fprintf(stderr,
        "Usage: %s --out DIR [options]\n"
        "\n"
        "  --out DIR          Output directory (required)\n"
        "  --frames N         Max frames (0 = unlimited, default 0)\n"
        "  --fps N            FPS: 15, 30, 60, 100 (default 30)\n"
        "  --resolution NAME  HD720, HD1080, HD2K, VGA (default HD720)\n"
        "  --num-disp N       SGBM num disparities, multiple of 16 (default 128)\n"
        "  --block-size N     SGBM block size, odd integer >= 5 (default 7)\n"
        "  --ocl              Enable OpenCV OpenCL (Intel iGPU / AMD via Mesa)\n"
        "\n"
        "First run needs internet: calibration is downloaded via wget and cached.\n",
        prog);
}

static sl_oc::video::RESOLUTION parse_resolution(const std::string& s) {
    if (s == "HD1080") return sl_oc::video::RESOLUTION::HD1080;
    if (s == "HD2K")   return sl_oc::video::RESOLUTION::HD2K;
    if (s == "VGA")    return sl_oc::video::RESOLUTION::VGA;
    return sl_oc::video::RESOLUTION::HD720;
}

static sl_oc::video::FPS parse_fps(int v) {
    if (v == 15)  return sl_oc::video::FPS::FPS_15;
    if (v == 60)  return sl_oc::video::FPS::FPS_60;
    if (v == 100) return sl_oc::video::FPS::FPS_100;
    return sl_oc::video::FPS::FPS_30;
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

int main(int argc, char* argv[]) {
    std::string out_dir;
    int max_frames = 0, fps_val = 30, num_disp = 128, block_size = 7;
    std::string res_str = "HD720";
    bool use_ocl = false;

    static const struct option long_opts[] = {
        {"out",        required_argument, nullptr, 'o'},
        {"frames",     required_argument, nullptr, 'n'},
        {"fps",        required_argument, nullptr, 'f'},
        {"resolution", required_argument, nullptr, 'r'},
        {"num-disp",   required_argument, nullptr, 'd'},
        {"block-size", required_argument, nullptr, 'b'},
        {"ocl",        no_argument,       nullptr, 'c'},
        {nullptr, 0, nullptr, 0}
    };

    int opt, idx = 0;
    while ((opt = getopt_long(argc, argv, "o:n:f:r:d:b:c", long_opts, &idx)) != -1) {
        switch (opt) {
            case 'o': out_dir    = optarg;            break;
            case 'n': max_frames = std::stoi(optarg); break;
            case 'f': fps_val    = std::stoi(optarg); break;
            case 'r': res_str    = optarg;            break;
            case 'd': num_disp   = std::stoi(optarg); break;
            case 'b': block_size = std::stoi(optarg); break;
            case 'c': use_ocl    = true;              break;
            default:  print_usage(argv[0]); return 1;
        }
    }

    if (out_dir.empty()) {
        fprintf(stderr, "ERROR: --out DIR is required\n\n");
        print_usage(argv[0]);
        return 1;
    }

    num_disp   = std::max(16, (num_disp / 16) * 16);
    block_size = (block_size < 5) ? 5 : (block_size % 2 == 0 ? block_size + 1 : block_size);

    signal(SIGINT,  on_signal);
    signal(SIGTERM, on_signal);

    // OpenCL
    if (use_ocl) {
        cv::ocl::setUseOpenCL(true);
        if (cv::ocl::haveOpenCL()) {
            cv::ocl::Context ctx;
            if (ctx.create(cv::ocl::Device::TYPE_GPU))
                fprintf(stdout, "OpenCL: device '%s'\n", ctx.device(0).name().c_str());
            else
                fprintf(stdout, "OpenCL: no GPU device, using CPU\n");
        } else {
            fprintf(stdout, "OpenCL: not available in this OpenCV build\n");
        }
    } else {
        cv::ocl::setUseOpenCL(false);
    }

    // Output dirs
    fs::create_directories(out_dir + "/rgb");
    fs::create_directories(out_dir + "/depth_png");

    // Open camera
    sl_oc::video::VideoParams params;
    params.res     = parse_resolution(res_str);
    params.fps     = parse_fps(fps_val);
    params.verbose = sl_oc::VERBOSITY::INFO;

    sl_oc::video::VideoCapture cap(params);
    if (!cap.initializeVideo(-1)) {
        fprintf(stderr, "ERROR: Could not open ZED camera. "
                "Check USB connection and udev rules (scripts/udev-install-fedora.sh).\n");
        return 2;
    }

    int sn = cap.getSerialNumber();
    fprintf(stdout, "ZED camera SN=%d  resolution=%s  fps=%d\n", sn, res_str.c_str(), fps_val);

    // Get frame dimensions
    int full_w = 0, img_h = 0;
    cap.getFrameSize(full_w, img_h);
    const int img_w = full_w / 2;
    fprintf(stdout, "Frame: %dx%d per eye\n", img_w, img_h);

    // Load calibration
    CalibResult calib;
    if (!load_calibration(sn, cv::Size(img_w, img_h), calib))
        return 4;

    const double fx          = calib.cam_l.at<double>(0, 0);
    const double fy          = calib.cam_l.at<double>(1, 1);
    const double cx          = calib.cam_l.at<double>(0, 2);
    const double cy          = calib.cam_l.at<double>(1, 2);
    const double baseline_mm = calib.baseline_mm;

    fprintf(stdout, "Calibration: fx=%.2f fy=%.2f cx=%.2f cy=%.2f baseline=%.2f mm\n",
            fx, fy, cx, cy, baseline_mm);

    {
        FILE* f = fopen((out_dir + "/calibration.json").c_str(), "w");
        if (!f) { perror("calibration.json"); return 5; }
        fprintf(f,
            "{\n"
            "  \"fx\": %.6f,\n  \"fy\": %.6f,\n  \"cx\": %.6f,\n  \"cy\": %.6f,\n"
            "  \"baseline_mm\": %.6f,\n  \"baseline_m\": %.6f,\n"
            "  \"image_width\": %d,\n  \"image_height\": %d,\n"
            "  \"depth_units\": \"millimeters\",\n"
            "  \"serial_number\": %d,\n  \"resolution\": \"%s\"\n"
            "}\n",
            fx, fy, cx, cy, baseline_mm, baseline_mm / 1000.0,
            img_w, img_h, sn, res_str.c_str());
        fclose(f);
    }

    // SGBM
    const int P1 = 8  * 3 * block_size * block_size;
    const int P2 = 32 * 3 * block_size * block_size;
    auto sgbm = cv::StereoSGBM::create(
        0, num_disp, block_size, P1, P2, 1, 63, 10, 100, 32,
        cv::StereoSGBM::MODE_SGBM);

    FILE* rgb_txt = fopen((out_dir + "/rgb.txt").c_str(),   "w");
    FILE* dep_txt = fopen((out_dir + "/depth.txt").c_str(), "w");
    if (!rgb_txt || !dep_txt) { perror("open txt"); return 5; }
    fprintf(rgb_txt, "# timestamp filename\n");
    fprintf(dep_txt, "# timestamp filename\n");

    fprintf(stdout, "Recording to %s  (Ctrl+C to stop%s)\n",
            out_dir.c_str(),
            max_frames > 0
                ? (std::string(", ") + std::to_string(max_frames) + " frames").c_str()
                : "");

    int      n   = 0;
    uint64_t lts = 0;
    int      err = 0;

    while (!g_stop && (max_frames == 0 || n < max_frames)) {
        const sl_oc::video::Frame frame = cap.getLastFrame();
        if (frame.data == nullptr || frame.timestamp == lts) {
            if (++err > 500) { fprintf(stderr, "No frames for 5s — disconnected?\n"); break; }
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            continue;
        }
        err = 0;
        lts = frame.timestamp;

        cv::Mat yuv(img_h, full_w, CV_8UC2, frame.data);
        cv::Mat bgr;
        cv::cvtColor(yuv, bgr, cv::COLOR_YUV2BGR_YUYV);
        cv::Mat lr = bgr(cv::Rect(0,     0, img_w, img_h));
        cv::Mat rr = bgr(cv::Rect(img_w, 0, img_w, img_h));

        cv::Mat lrect, rrect;
        cv::remap(lr, lrect, calib.map_lx, calib.map_ly, cv::INTER_LINEAR);
        cv::remap(rr, rrect, calib.map_rx, calib.map_ry, cv::INTER_LINEAR);

        cv::Mat lg, rg, disp;
        cv::cvtColor(lrect, lg, cv::COLOR_BGR2GRAY);
        cv::cvtColor(rrect, rg, cv::COLOR_BGR2GRAY);
        sgbm->compute(lg, rg, disp);

        // depth_mm = fx * baseline_mm / disparity_px
        cv::Mat df;
        disp.convertTo(df, CV_32F, 1.0 / 16.0);
        cv::Mat depth_f = cv::Mat::zeros(df.size(), CV_32F);
        cv::divide(static_cast<float>(fx * baseline_mm), df, depth_f);
        depth_f.setTo(0.f, df <= 0.5f);
        cv::Mat depth_mm;
        depth_f.convertTo(depth_mm, CV_16UC1);

        char stem[16];
        snprintf(stem, sizeof(stem), "%06d", n);
        const std::string rp = std::string("rgb/")       + stem + ".png";
        const std::string dp = std::string("depth_png/") + stem + ".png";

        cv::imwrite(out_dir + "/" + rp, lrect);
        cv::imwrite(out_dir + "/" + dp, depth_mm);

        const double ts = static_cast<double>(frame.timestamp) * 1e-9;
        fprintf(rgb_txt, "%.9f %s\n", ts, rp.c_str());
        fprintf(dep_txt, "%.9f %s\n", ts, dp.c_str());

        if (++n % 30 == 0) { fflush(stdout); fprintf(stdout, "  %d frames\n", n); }
    }

    fclose(rgb_txt);
    fclose(dep_txt);

    {
        FILE* f = fopen((out_dir + "/metadata.json").c_str(), "w");
        if (f) {
            fprintf(f, "{\n  \"total_frames\": %d,\n  \"fps\": %d,\n"
                    "  \"resolution\": \"%s\",\n  \"sgbm_num_disp\": %d,\n"
                    "  \"sgbm_block_size\": %d,\n  \"serial_number\": %d,\n"
                    "  \"ocl_enabled\": %s\n}\n",
                    n, fps_val, res_str.c_str(), num_disp, block_size, sn,
                    use_ocl ? "true" : "false");
            fclose(f);
        }
    }

    fprintf(stdout, "Done. %d frames → %s\n", n, out_dir.c_str());
    return 0;
}
