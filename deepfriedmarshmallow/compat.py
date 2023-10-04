import sys

if sys.version_info[0] >= 3:

    def is_overridden(instance_func, class_func):
        # type: (MethodType, MethodType) -> bool
        return instance_func.__func__ is not class_func

else:

    def is_overridden(instance_func, class_func):
        # type: (MethodType, MethodType) -> bool
        return instance_func.__func__ is not class_func.__func__
