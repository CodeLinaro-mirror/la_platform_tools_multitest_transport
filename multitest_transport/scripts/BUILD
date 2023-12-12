# MTT init scripts.

load("//third_party/bazel_rules/rules_python/python:py_test.bzl", "py_test")
load("@tradefed_cluster//tradefed_cluster:adapter.bzl", "third_party")

package(default_applicable_licenses = ["//multitest_transport:license"])

licenses(["notice"])

filegroup(
    name = "scripts",
    srcs = glob(
        ["**"],
        exclude = [
            "BUILD",
            "**/*_test.py",
        ],
    ),
    visibility = ["//multitest_transport"],
)

py_test(
    name = "gen_subnets_test",
    srcs = [
        "gen_subnets.py",
        "gen_subnets_test.py",
    ],
    deps = [
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
    ],
)
