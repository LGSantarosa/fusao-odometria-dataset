// Stereo ORB-SLAM3 over extracted PNGs; logs the pose emitted at each frame (causal) + indicators.
#include <System.h>
#include <Tracking.h>
#include <opencv2/opencv.hpp>
#include <chrono>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <thread>

int main(int argc, char** argv) {
    if (argc != 5) { std::cerr << "usage: vocab settings seq_dir out_dir\n"; return 1; }
    std::string seq = argv[3], out = argv[4];
    std::ifstream st(seq + "/images/stamps.csv");
    std::string line; std::getline(st, line);  // header
    std::vector<long long> ts;
    while (std::getline(st, line)) if (!line.empty()) ts.push_back(std::stoll(line));
    ORB_SLAM3::System slam(argv[1], argv[2], ORB_SLAM3::System::STEREO, false);
    const double rate = std::getenv("VO_RATE") ? std::atof(std::getenv("VO_RATE")) : 1.0;  // tempo real
    const auto wall0 = std::chrono::steady_clock::now();
    const long long t0 = ts.empty() ? 0 : ts.front();
    std::ofstream f(out + "/frames.csv");
    f << "ts_ns,ok,map_id,inliers,n_features,reproj_err,tracked_ratio,x,y,z,qx,qy,qz,qw\n" << std::setprecision(9) << std::fixed;
    for (long long t : ts) {
        cv::Mat L = cv::imread(seq + "/images/left/" + std::to_string(t) + ".png", cv::IMREAD_GRAYSCALE);
        cv::Mat R = cv::imread(seq + "/images/right/" + std::to_string(t) + ".png", cv::IMREAD_GRAYSCALE);
        if (rate > 0)  // espera o instante do frame: as threads de mapeamento acompanham como online
            std::this_thread::sleep_until(wall0 + std::chrono::nanoseconds((long long)((t - t0) / rate)));
        Sophus::SE3f Tcw = slam.TrackStereo(L, R, t * 1e-9);
        auto* tr = slam.GetTracker();
        bool ok = slam.GetTrackingState() == ORB_SLAM3::Tracking::OK;
        f << t << "," << ok << "," << slam.GetActiveMapId() << "," << tr->mLogInliers << "," << tr->mLogNFeatures
          << "," << tr->mLogReprojErr << "," << tr->mLogTrackedRatio;
        if (ok) {
            Sophus::SE3f Twc = Tcw.inverse();
            Eigen::Vector3f p = Twc.translation(); Eigen::Quaternionf q = Twc.unit_quaternion();
            f << "," << p.x() << "," << p.y() << "," << p.z() << "," << q.x() << "," << q.y() << "," << q.z() << "," << q.w();
        } else f << ",,,,,,,";
        f << "\n";
    }
    slam.Shutdown();
}
