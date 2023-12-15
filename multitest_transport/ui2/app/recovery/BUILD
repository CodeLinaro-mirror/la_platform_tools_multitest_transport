load("//multitest_transport:adapter.bzl", "ng_module", "per_file_sass_binaries", "third_party_js")

package(default_applicable_licenses = ["//multitest_transport:license"])

licenses(["notice"])

per_file_sass_binaries(
    name = "styles",
    srcs = glob(["*.scss"]),
    deps = [
        "//multitest_transport/ui2:constants",
        "//multitest_transport/ui2/app/shared:shared_styles",
    ],
)

ng_module(
    name = "recovery",
    srcs = [
        "recovery_device_list.ts",
        "recovery_host_list.ts",
        "recovery_host_status.ts",
        "recovery_module.ts",
        "recovery_page.ts",
        "recovery_setting_page.ts",
    ],
    assets = [
        ":styles",
        "recovery_device_list.ng.html",
        "recovery_host_list.ng.html",
        "recovery_host_status.ng.html",
        "recovery_page.ng.html",
        "recovery_setting_page.ng.html",
    ],
    strict_templates = False,
    visibility = ["//multitest_transport"],
    deps = [
        third_party_js("angular2:core"),
        third_party_js("angular2:platform_browser"),
        third_party_js("angular2:router"),
        third_party_js("angular_components:cdk_a11y"),
        third_party_js("angular_components:cdk_collections"),
        third_party_js("angular_components:material_dialog"),
        third_party_js("angular_components:material_table"),
        third_party_js("rxjs"),
        "//multitest_transport/ui2/app/devices",
        "//multitest_transport/ui2/app/hosts",
        "//multitest_transport/ui2/app/notes",
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/shared",
    ],
)

ng_module(
    name = "tests",
    testonly = True,
    srcs = [
        "recovery_device_list_test.ts",
        "recovery_host_list_test.ts",
        "recovery_host_status_test.ts",
        "recovery_page_test.ts",
        "recovery_setting_page_test.ts",
    ],
    visibility = ["//multitest_transport"],
    deps = [
        ":recovery",
        third_party_js("angular2:common_http_testing"),
        third_party_js("angular2:core"),
        third_party_js("angular2:core_testing"),
        third_party_js("angular2:platform_browser_animations"),
        third_party_js("angular2:router"),
        third_party_js("angular2:router_testing"),
        third_party_js("angular_components:material_dialog"),
        third_party_js("rxjs"),
        third_party_js("typings/jasmine"),
        "//multitest_transport/ui2/app/hosts",
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/testing:angular_util",
        "//multitest_transport/ui2/app/testing:jasmine_util",
        "//multitest_transport/ui2/app/testing:test_util",
    ],
)
