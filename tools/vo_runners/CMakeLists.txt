cmake_minimum_required(VERSION 3.16)
project(vo_runners CXX)
set(CMAKE_CXX_STANDARD 17)
# Bibliotecas de third_party/ ficam fora do caminho do sistema: gravar o RPATH no binário.
set(CMAKE_BUILD_WITH_INSTALL_RPATH OFF)
# RPATH (não RUNPATH): também vale para dependências transitivas (libpango_display -> libpango_windowing).
add_link_options(-Wl,--disable-new-dtags)
set(CMAKE_BUILD_RPATH "${CMAKE_PREFIX_PATH}/lib")
if(ORB_SLAM3_DIR)
  list(APPEND CMAKE_BUILD_RPATH ${ORB_SLAM3_DIR}/lib ${ORB_SLAM3_DIR}/Thirdparty/DBoW2/lib ${ORB_SLAM3_DIR}/Thirdparty/g2o/lib)
endif()
find_package(OpenCV 4 REQUIRED)
find_package(Eigen3 REQUIRED)
if(ORB_SLAM3_DIR)
  find_package(Pangolin REQUIRED)
  add_executable(orbslam3_stereo_log orbslam3_stereo_log.cc)
  target_include_directories(orbslam3_stereo_log PRIVATE ${ORB_SLAM3_DIR} ${ORB_SLAM3_DIR}/include
    ${ORB_SLAM3_DIR}/include/CameraModels ${ORB_SLAM3_DIR}/Thirdparty/Sophus ${EIGEN3_INCLUDE_DIR})
  target_link_libraries(orbslam3_stereo_log ${ORB_SLAM3_DIR}/lib/libORB_SLAM3.so
    ${ORB_SLAM3_DIR}/Thirdparty/DBoW2/lib/libDBoW2.so ${ORB_SLAM3_DIR}/Thirdparty/g2o/lib/libg2o.so
    ${OpenCV_LIBS} ${Pangolin_LIBRARIES} pthread)
endif()
if(STELLA_PREFIX)
  find_package(stella_vslam REQUIRED PATHS ${STELLA_PREFIX})
  add_executable(stella_stereo_log stella_stereo_log.cc)
  target_link_libraries(stella_stereo_log stella_vslam::stella_vslam ${OpenCV_LIBS} yaml-cpp)
endif()
