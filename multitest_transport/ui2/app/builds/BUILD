load("//multitest_transport:adapter.bzl", "ng_module", "sass_binary", "third_party_js")

package(default_applicable_licenses = ["//multitest_transport:license"])

licenses(["notice"])

sass_binary(
    name = "build_create_page",
    src = "build_create_page.scss",
    output_name = "build_create_page.css",
    visibility = ["//multitest_transport"],
)

sass_binary(
    name = "build_detail",
    src = "build_detail.scss",
    output_name = "build_detail.css",
    visibility = ["//multitest_transport"],
    deps = [
        "//multitest_transport/ui2:constants",
        "//multitest_transport/ui2/app/shared:shared_styles",
    ],
)

sass_binary(
    name = "build_editor",
    src = "build_editor.scss",
    output_name = "build_editor.css",
    visibility = ["//multitest_transport"],
)

sass_binary(
    name = "build_file_selector",
    src = "build_file_selector.scss",
    output_name = "build_file_selector.css",
    visibility = ["//multitest_transport"],
)

sass_binary(
    name = "build_list",
    src = "build_list.scss",
    output_name = "build_list.css",
    visibility = ["//multitest_transport"],
)

sass_binary(
    name = "xts_requirement_detect",
    src = "xts_requirement_detect.scss",
    output_name = "xts_requirement_detect.css",
    visibility = ["//multitest_transport"],
)

ng_module(
    name = "builds",
    srcs = [
        "build_create_page.ts",
        "build_detail.ts",
        "build_detail_page.ts",
        "build_editor.ts",
        "build_file_selector.ts",
        "build_list.ts",
        "build_list_page.ts",
        "builds_module.ts",
        "xts_requirement_detect.ts",
    ],
    assets = [
        ":build_create_page",
        ":build_detail",
        ":build_editor",
        ":build_file_selector",
        ":build_list",
        ":xts_requirement_detect",
        "build_create_page.ng.html",
        "build_detail.ng.html",
        "build_detail_page.ng.html",
        "build_editor.ng.html",
        "build_file_selector.ng.html",
        "build_list.ng.html",
        "build_list_page.ng.html",
        "xts_requirement_detect.ng.html",
    ],
    visibility = ["//multitest_transport"],
    deps = [
        third_party_js("angular2:core"),
        third_party_js("angular2:platform_browser"),
        third_party_js("angular2:router"),
        third_party_js("angular_components:cdk_a11y"),
        third_party_js("angular_components:cdk_collections"),
        third_party_js("angular_components:cdk_keycodes"),
        third_party_js("angular_components:material_button"),
        third_party_js("angular_components:material_chips"),
        third_party_js("angular_components:material_dialog"),
        third_party_js("angular_components:material_stepper"),
        third_party_js("angular_components:material_table"),
        third_party_js("rxjs"),
        "//multitest_transport/ui2/app/build_channels",
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/shared",
        "//multitest_transport/ui2/app/test_runs",
    ],
)

ng_module(
    name = "tests",
    testonly = True,
    srcs = [
        "build_create_page_test.ts",
        "build_detail_test.ts",
        "build_editor_test.ts",
        "build_file_selector_test.ts",
        "build_list_test.ts",
        "xts_requirement_detect_test.ts",
    ],
    visibility = ["//multitest_transport"],
    deps = [
        ":builds",
        third_party_js("angular2:core"),
        third_party_js("angular2:core_testing"),
        third_party_js("angular2:platform_browser_animations"),
        third_party_js("angular2:router"),
        third_party_js("angular2:router_testing"),
        third_party_js("angular_components:cdk_a11y"),
        third_party_js("angular_components:material_chips"),
        third_party_js("angular_components:material_dialog"),
        third_party_js("rxjs"),
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/testing:jasmine_util",
        "//multitest_transport/ui2/app/testing:test_util",
    ],
)
