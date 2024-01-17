load("//multitest_transport:adapter.bzl", "ng_module", "per_file_sass_binaries", "third_party_js")

package(default_applicable_licenses = ["//multitest_transport:license"])

licenses(["notice"])

per_file_sass_binaries(
    name = "styles",
    srcs = glob(["*.scss"]),
    visibility = ["//visibility:private"],
    deps = [
        "//multitest_transport/ui2:constants",
        "//multitest_transport/ui2/app/shared:shared_styles",
    ],
)

ng_module(
    name = "devices",
    srcs = [
        "device_details.ts",
        "device_details_extra_infos.ts",
        "device_details_history.ts",
        "device_details_page.ts",
        "device_details_summary.ts",
        "device_list.ts",
        "device_list_page.ts",
        "device_list_table.ts",
        "devices_module.ts",
        "simple_device_list.ts",
    ],
    assets = [
        ":styles",
        "device_details.ng.html",
        "device_details_extra_infos.ng.html",
        "device_details_history.ng.html",
        "device_details_page.ng.html",
        "device_details_summary.ng.html",
        "device_list.ng.html",
        "device_list_page.ng.html",
        "device_list_table.ng.html",
        "simple_device_list.ng.html",
    ],
    slow_development_build = True,
    strict_templates = False,
    visibility = ["//multitest_transport"],
    deps = [
        third_party_js("angular2:core"),
        third_party_js("angular2:forms"),
        third_party_js("angular2:platform_browser"),
        third_party_js("angular2:router"),
        third_party_js("angular_components:cdk_a11y"),
        third_party_js("angular_components:cdk_collections"),
        third_party_js("angular_components:material_autocomplete"),
        third_party_js("angular_components:material_dialog"),
        third_party_js("angular_components:material_sort"),
        third_party_js("angular_components:material_table"),
        third_party_js("angular_components:material_tabs"),
        third_party_js("rxjs"),
        "//multitest_transport/ui2/app/notes",
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/shared",
    ],
)

ng_module(
    name = "tests",
    testonly = True,
    srcs = [
        "device_details_extra_infos_test.ts",
        "device_details_history_test.ts",
        "device_details_page_test.ts",
        "device_details_summary_test.ts",
        "device_details_test.ts",
        "device_list_table_test.ts",
        "device_list_test.ts",
        "simple_device_list_test.ts",
    ],
    visibility = ["//multitest_transport"],
    deps = [
        ":devices",
        third_party_js("angular2:common_http_testing"),
        third_party_js("angular2:core"),
        third_party_js("angular2:core_testing"),
        third_party_js("angular2:platform_browser"),
        third_party_js("angular2:platform_browser_animations"),
        third_party_js("angular2:router"),
        third_party_js("angular2:router_testing"),
        third_party_js("angular_components:material_dialog"),
        third_party_js("angular_components:material_sort"),
        third_party_js("rxjs"),
        third_party_js("typings/jasmine"),
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/shared",
        "//multitest_transport/ui2/app/testing:angular_util",
        "//multitest_transport/ui2/app/testing:jasmine_util",
        "//multitest_transport/ui2/app/testing:test_util",
    ],
)
