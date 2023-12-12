# Sidekick services for Multi-Test Transport.
load("@tradefed_cluster//tradefed_cluster:adapter.bzl", "py_test", "pytype_strict_library", "third_party")

package(default_applicable_licenses = ["//multitest_transport:license"])

licenses(["notice"])

pytype_strict_library(
    name = "sidekicks",
    srcs = [
        "main.py",
    ],
    visibility = ["//multitest_transport"],
    deps = [
        "//multitest_transport/test_scheduler:download_util_lib",
        "//multitest_transport/util",
        third_party("flask"),
    ],
)

py_test(
    name = "main_test",
    srcs = [
        "main_test.py",
    ],
    deps = [
        ":sidekicks",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "//multitest_transport/test_scheduler:download_util_lib",
        "//multitest_transport/util:analytics_lib",
        "//multitest_transport/util:tfc_client_lib",
        "@tradefed_cluster//tradefed_cluster:api_messages_lib",
        third_party("absl/testing:absltest"),
        third_party("webtest"),
    ],
)
