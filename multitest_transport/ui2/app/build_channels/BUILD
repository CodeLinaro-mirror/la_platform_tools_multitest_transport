load("//multitest_transport:adapter.bzl", "ng_module", "per_file_sass_binaries", "third_party_js")

package(default_applicable_licenses = ["//multitest_transport:license"])

licenses(["notice"])

per_file_sass_binaries(
    name = "styles",
    srcs = glob(["*.scss"]),
    visibility = ["//visibility:private"],
    deps = ["//multitest_transport/ui2:constants"],
)

ng_module(
    name = "build_channels",
    srcs = [
        "build_channel_edit_page.ts",
        "build_channel_item.ts",
        "build_channel_list.ts",
        "build_channels_module.ts",
        "build_picker.ts",
        "test_resource_form.ts",
    ],
    assets = [
        ":styles",
        "build_channel_edit_page.ng.html",
        "build_channel_item.ng.html",
        "build_channel_list.ng.html",
        "build_picker.ng.html",
        "test_resource_form.ng.html",
    ],
    strict_templates = False,
    visibility = ["//multitest_transport"],
    deps = [
        third_party_js("angular_components:cdk_a11y"),
        third_party_js("angular_components:cdk_collections"),
        third_party_js("angular2:core"),
        third_party_js("angular2:forms"),
        third_party_js("angular_components:material_button"),
        third_party_js("angular_components:material_dialog"),
        third_party_js("angular_components:material_table"),
        third_party_js("angular_components:material_tabs"),
        third_party_js("angular2:router"),
        third_party_js("rxjs"),
        third_party_js("typings/jasmine"),
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/shared",
    ],
)

ng_module(
    name = "tests",
    testonly = True,
    srcs = [
        "build_channel_edit_page_test.ts",
        "build_channel_item_test.ts",
        "build_channel_list_test.ts",
        "build_picker_test.ts",
        "test_resource_form_test.ts",
    ],
    visibility = ["//multitest_transport"],
    deps = [
        ":build_channels",
        third_party_js("angular_components:cdk_a11y"),
        third_party_js("angular2:core"),
        third_party_js("angular2:core_testing"),
        third_party_js("angular_components:material_dialog"),
        third_party_js("angular2:platform_browser_animations"),
        third_party_js("angular2:router"),
        third_party_js("angular2:router_testing"),
        third_party_js("rxjs"),
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/testing:jasmine_util",
        "//multitest_transport/ui2/app/testing:test_util",
    ],
)
