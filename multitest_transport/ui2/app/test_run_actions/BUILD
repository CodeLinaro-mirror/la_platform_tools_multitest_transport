load("//multitest_transport:adapter.bzl", "ng_module", "per_file_sass_binaries", "third_party_js")

package(default_applicable_licenses = ["//multitest_transport:license"])

licenses(["notice"])

per_file_sass_binaries(
    name = "styles",
    srcs = glob(["*.scss"]),
    deps = [
        "//multitest_transport/ui2:constants",
    ],
)

ng_module(
    name = "test_run_actions",
    srcs = [
        "test_run_action_edit_page.ts",
        "test_run_action_list.ts",
        "test_run_action_picker.ts",
        "test_run_action_picker_dialog.ts",
        "test_run_actions_module.ts",
    ],
    assets = [
        ":styles",
        "test_run_action_edit_page.ng.html",
        "test_run_action_list.ng.html",
        "test_run_action_picker.ng.html",
        "test_run_action_picker_dialog.ng.html",
    ],
    strict_templates = False,
    visibility = ["//multitest_transport"],
    deps = [
        third_party_js("angular_components:cdk_a11y"),
        third_party_js("angular_components:cdk_collections"),
        third_party_js("angular_components:cdk_drag_drop"),
        third_party_js("angular_components:material_button"),
        third_party_js("angular_components:material_list"),
        third_party_js("angular_components:material_legacy_dialog"),
        third_party_js("angular2:core"),
        third_party_js("angular2:router"),
        third_party_js("rxjs"),
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/shared",
    ],
)

ng_module(
    name = "tests",
    testonly = True,
    srcs = [
        "test_run_action_edit_page_test.ts",
        "test_run_action_list_test.ts",
        "test_run_action_picker_dialog_test.ts",
        "test_run_action_picker_test.ts",
    ],
    visibility = ["//multitest_transport"],
    deps = [
        ":test_run_actions",
        third_party_js("angular_components:cdk_a11y"),
        third_party_js("angular_components:material_legacy_dialog"),
        third_party_js("angular2:core"),
        third_party_js("angular2:core_testing"),
        third_party_js("angular2:platform_browser_animations"),
        third_party_js("angular2:router"),
        third_party_js("angular2:router_testing"),
        third_party_js("rxjs"),
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/testing:jasmine_util",
    ],
)
