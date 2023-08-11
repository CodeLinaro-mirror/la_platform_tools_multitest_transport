load("//multitest_transport:adapter.bzl", "ng_module", "per_file_sass_binaries", "third_party_js")

package(default_applicable_licenses = ["//multitest_transport:license"])

# MTT service package
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
    name = "notes",
    srcs = [
        "add_notes_button.ts",
        "note_list.ts",
        "notes_dialog.ts",
        "notes_editor.ts",
        "notes_module.ts",
        "predefined_message_list.ts",
        "predefined_messages_editor.ts",
    ],
    assets = [
        ":styles",
        "add_notes_button.ng.html",
        "note_list.ng.html",
        "notes_dialog.ng.html",
        "notes_editor.ng.html",
        "predefined_message_list.ng.html",
        "predefined_messages_editor.ng.html",
    ],
    strict_templates = False,
    visibility = ["//multitest_transport"],
    deps = [
        third_party_js("angular_components:cdk_a11y"),
        third_party_js("angular2:core"),
        third_party_js("angular2:common_http"),
        third_party_js("angular2:forms"),
        third_party_js("angular_components:material_legacy_dialog"),
        third_party_js("angular_components:material_table"),
        third_party_js("angular_components:material_sort"),
        third_party_js("angular2:router"),
        third_party_js("moment:typings"),
        third_party_js("rxjs"),
        "//multitest_transport/ui2/app/services",
        "//multitest_transport/ui2/app/shared",
    ],
)

ng_module(
    name = "tests",
    testonly = True,
    srcs = [
        "add_notes_button_test.ts",
        "note_list_test.ts",
        "notes_dialog_test.ts",
        "notes_editor_test.ts",
        "predefined_message_list_test.ts",
        "predefined_messages_editor_test.ts",
    ],
    visibility = ["//multitest_transport"],
    deps = [
        ":notes",
        "//third_party/javascript/angular2:common_http_testing",
        third_party_js("angular2:core"),
        third_party_js("angular2:core_testing"),
        third_party_js("angular2:common_http"),
        third_party_js("angular_components:material_legacy_dialog"),
        third_party_js("angular2:platform_browser_animations"),
        third_party_js("angular2:router"),
        third_party_js("angular2:router_testing"),
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
