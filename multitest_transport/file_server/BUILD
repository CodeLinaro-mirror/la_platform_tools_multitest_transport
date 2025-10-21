# Android Test Station local file server.

load("//third_party/bazel_rules/rules_python/python:py_test.bzl", "py_test")
load("@tradefed_cluster//tradefed_cluster:adapter.bzl", "py_library", "py_strict_test", "pytype_strict_binary", "pytype_strict_library", "third_party")

package(default_applicable_licenses = ["//multitest_transport:license"])

licenses(["notice"])

# TODO: change to pytype_strict_library once b/168841142 is fixed.
py_library(
    name = "file_server_lib",
    srcs = [
        "file_server.py",
        "gunicorn_config.py",
    ],
    visibility = ["//multitest_transport"],
    deps = [
        third_party("absl:app"),
        third_party("absl/flags"),
        third_party("attr"),
        third_party("flask"),
        third_party("werkzeug"),
        "//third_party/py/flask:flask_without_jinja",
        "//multitest_transport/models:ndb_models_lib",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
    ],
)

py_strict_test(
    name = "file_server_test",
    srcs = [
        "file_server_test.py",
    ],
    data = [
        "//javatests/com/google/devtools/mobileharness/shared/util/cache/persistent:testdata",
    ],
    deps = [
        ":file_server_lib",
        "//pyglib:resources",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
        third_party("werkzeug"),
        "//multitest_transport/models:ndb_models_lib",
        "@tradefed_cluster//tradefed_cluster/util:ndb_test_lib",
    ],
)

pytype_strict_binary(
    name = "file_server",
    srcs = ["file_server.py"],
    main = "file_server.py",
    deps = [
        ":file_server_lib",
        third_party("absl:app"),
        third_party("absl/flags"),
        third_party("flask"),
    ],
)

pytype_strict_library(
    name = "proxy_lib",
    srcs = [
        "proxy.py",
    ],
    visibility = ["//multitest_transport"],
    deps = [
        "//multitest_transport/util",
        third_party("flask"),
    ],
)

py_test(
    name = "proxy_test",
    srcs = [
        "proxy_test.py",
    ],
    deps = [
        ":proxy_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        third_party("absl/testing:absltest"),
        third_party("webtest"),
    ],
)
