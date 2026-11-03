idf_component_register(SRC_DIRS "src"
                       INCLUDE_DIRS "include"
                       REQUIRES esp_wifi esp_timer esp-radar nvs_flash)
message(STATUS "Building esp_wifi_sensing")
include(package_manager)
cu_pkg_define_version(${CMAKE_CURRENT_LIST_DIR})
message(STATUS "Using local esp_wifi_sensing library")
target_compile_options(${COMPONENT_LIB} PRIVATE "-Wno-format")
