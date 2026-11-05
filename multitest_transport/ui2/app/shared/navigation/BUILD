load("//multitest_transport:adapter.bzl", "ng_module", "third_party_js")

package(default_applicable_licenses = ["//multitest_transport:license"])

# Navigation strategies between MTT UI2 and the embedded LabConsole (MHFE V6) pages
licenses(["notice"])

ng_module(
    name = "navigation",
    srcs = [
        "device_detail_navigation_strategy.ts",
        "host_detail_navigation_strategy.ts",
        "index.ts",
        "navigation_strategy_registry.ts",
        "page_navigation_strategy.ts",
        "search_navigation_strategy.ts",
        "v6_navigation_service.ts",
    ],
    slow_development_build = True,
    visibility = ["//multitest_transport"],
    deps = [
        third_party_js("angular2:core"),
        "//third_party/javascript/safevalues",
        "//multitest_transport/ui2/app/services",
    ],
)

ng_module(
    name = "tests",
    testonly = True,
    srcs = [
        "navigation_strategy_registry_test.ts",
        "v6_navigation_service_test.ts",
    ],
    visibility = ["//multitest_transport"],
    deps = [
        ":navigation",
        third_party_js("angular2:core_testing"),
        third_party_js("typings/jasmine"),
        "//third_party/javascript/safevalues",
        "//multitest_transport/ui2/app/services",
    ],
)
