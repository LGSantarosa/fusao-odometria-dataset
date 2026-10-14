#include <stella_vslam/system.h>
#include <stella_vslam/config.h>
#include <stella_vslam/tracking_module.h>
#include <opencv2/opencv.hpp>
#include <Eigen/Geometry>
#include <chrono>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <thread>

int main(int argc, char** argv) {
    if (argc != 5) { std::cerr << "usage: vocab config seq_dir out_dir\n"; return 1; }
    std::string seq = argv[3], out = argv[4];
    const double rate = std::getenv("VO_RATE") ? std::atof(std::getenv("VO_RATE")) : 1.0;  // tempo real
    const auto wall0 = std::chrono::steady_clock::now();
    long long t0 = -1;
    auto cfg = std::make_shared<stella_vslam::config>(argv[2]);
    stella_vslam::system slam(cfg, argv[1]);
    slam.startup();
    slam.disable_loop_detector();
    std::ifstream st(seq + "/images/stamps.csv"); std::string line; std::getline(st, line);
    std::ofstream f(out + "/frames.csv");
    f << "ts_ns,ok,map_id,inliers,n_features,reproj_err,tracked_ratio,x,y,z,qx,qy,qz,qw\n" << std::setprecision(9) << std::fixed;
    int map_id = 0; bool prev_ok = false, started = false;
    while (std::getline(st, line)) {
        if (line.empty()) continue;
        long long t = std::stoll(line);
        cv::Mat L = cv::imread(seq + "/images/left/" + std::to_string(t) + ".png", cv::IMREAD_GRAYSCALE);
        cv::Mat R = cv::imread(seq + "/images/right/" + std::to_string(t) + ".png", cv::IMREAD_GRAYSCALE);
        if (t0 < 0) t0 = t;
        if (rate > 0)
            std::this_thread::sleep_until(wall0 + std::chrono::nanoseconds((long long)((t - t0) / rate)));
        // feed_stereo_frame devolve T_W_C (tracking_module::feed_frame -> get_pose_wc), não T_C_W
        auto Twc_ptr = slam.feed_stereo_frame(L, R, t * 1e-9);
        auto* tr = slam.get_tracker();
        bool ok = Twc_ptr && tr->tracking_state_ == stella_vslam::tracker_state_t::Tracking;
        if (ok && !prev_ok) { if (started) ++map_id; started = true; }  // novo mapa após perda/reinício
        prev_ok = ok;
        int nf = tr->last_n_features_;
        f << t << "," << ok << "," << map_id << "," << tr->last_inliers_ << "," << nf << ","
          << tr->last_reproj_err_ << "," << tr->last_tracked_ratio_;
        if (ok) {
            const Eigen::Matrix4d Twc = *Twc_ptr;
            Eigen::Quaterniond q(Twc.block<3, 3>(0, 0));
            f << "," << Twc(0, 3) << "," << Twc(1, 3) << "," << Twc(2, 3) << "," << q.x() << "," << q.y() << "," << q.z() << "," << q.w();
        } else f << ",,,,,,,";
        f << "\n";
    }
    slam.shutdown();
}
