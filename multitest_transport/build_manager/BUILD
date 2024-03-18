load("@tradefed_cluster//tradefed_cluster:adapter.bzl", "py_test", "pytype_strict_library", "third_party")

package(
    default_applicable_licenses = ["//multitest_transport:license"],
    default_visibility = ["//multitest_transport"],
)

licenses(["notice"])

pytype_strict_library(
    name = "xts_requirements_detector_lib",
    srcs = [
        "xts_requirements_detector.py",
    ],
    deps = [
        "//third_party/py/endpoints:endpoints_library",
        "//multitest_transport/models:messages_lib",
        "//multitest_transport/models:ndb_models_lib",
        "//multitest_transport/test_scheduler:test_kicker_lib",
        "//multitest_transport/util:analytics_lib",
        "//multitest_transport/util:apfe_client_lib",
        "//multitest_transport/util:constant_lib",
        "@tradefed_cluster//tradefed_cluster:common_lib",
        "@tradefed_cluster//tradefed_cluster/services:task_scheduler_lib",
        "@tradefed_cluster//tradefed_cluster/util:ndb_shim_lib",
        third_party("flask"),
        third_party("protorpc"),
        third_party("pytz"),
    ],
)

py_test(
    name = "xts_requirements_detector_test",
    srcs = [
        "xts_requirements_detector_test.py",
    ],
    tags = ["not_run:arm"],
    deps = [
        ":xts_requirements_detector_lib",
        "//third_party/py/google/protobuf:use_fast_cpp_protos",  # Automatically added go/proto_python_upb_flip
        "//multitest_transport/models",
        "@tradefed_cluster//tradefed_cluster:testbed_dependent_test_lib",
    ],
)
