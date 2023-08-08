# WebAOA device management
load("//multitest_transport:adapter.bzl", "ng_module", "per_file_sass_binaries", "third_party_js")

licenses(["notice"])

package(
    default_applicable_licenses = ["//multitest_transport:license"],
    default_visibility = ["//multitest_transport/tools/webaoa:__subpackages__"],
)

per_file_sass_binaries(
    name = "styles",
    srcs = glob(["*.scss"]),
)

ng_module(
    name = "device",
    srcs = [
        "device.ts",
        "device_list.ts",
        "device_manager.ts",
        "device_module.ts",
        "find_device_dialog.ts",
    ],
    assets = [
        ":styles",
        "device_list.ng.html",
    ],
    deps = [
        third_party_js("angular2:common"),
        third_party_js("angular2:core"),
        third_party_js("angular_components:material_icon"),
        third_party_js("angular_components:material_button"),
        third_party_js("angular_components:material_dialog"),
        third_party_js("angular_components:material_list"),
        third_party_js("typings/w3c_web_usb"),
        third_party_js("rxjs"),
    ],
)

ng_module(
    name = "tests",
    testonly = True,
    srcs = [
        "device_list_test.ts",
        "device_manager_test.ts",
        "device_test.ts",
    ],
    deps = [
        ":device",
        third_party_js("angular2:core"),
        third_party_js("angular2:core_testing"),
        third_party_js("rxjs"),
        "//multitest_transport/ui2/app/testing:jasmine_util",
    ],
)
