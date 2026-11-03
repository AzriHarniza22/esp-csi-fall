set(reqs esp_wifi_sensing
         protocol_examples_common
         driver
         freertos
         esp_driver_ledc
         led_strip
         esp_http_client
         mbedtls
         lwip
         esp_netif
         nvs_flash)

idf_component_register(SRCS "app_main.c"
                            "led_control.c"
                            "web_serial_monitor.c"
                            "wifi_runtime_manager.c"
                            "activity_classifier.c"
                            "ht_stimulus.c"
                            "tcp_stimulus.c"
                            "dns_stimulus.c"
                            "csi_phy_probe.c"
                       INCLUDE_DIRS "."
                       REQUIRES ${reqs}
                       PRIV_REQUIRES esp_driver_usb_serial_jtag)
