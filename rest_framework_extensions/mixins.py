import logging

from django.core.exceptions import FieldError
from django.http import Http404
from django.utils.encoding import force_str

from rest_framework_extensions.cache.mixins import CacheResponseMixin
# from rest_framework_extensions.etag.mixins import ReadOnlyETAGMixin, ETAGMixin
from rest_framework_extensions.bulk_operations.mixins import ListUpdateModelMixin, ListDestroyModelMixin
from rest_framework_extensions.settings import extensions_api_settings


logger = logging.getLogger('rest_framework_extensions.request')


class DetailSerializerMixin:
    """
    Add custom serializer for detail view
    """
    serializer_detail_class = None
    queryset_detail = None

    def get_serializer_class(self):
        error_message = "'{0}' should include a 'serializer_detail_class' attribute".format(
            self.__class__.__name__)
        assert self.serializer_detail_class is not None, error_message
        if self._is_request_to_detail_endpoint():
            return self.serializer_detail_class
        else:
            return super().get_serializer_class()

    def get_queryset(self, *args, **kwargs):
        if self._is_request_to_detail_endpoint() and self.queryset_detail is not None:
            return self.queryset_detail.all()  # todo: test all()
        else:
            return super().get_queryset(*args, **kwargs)

    def _is_request_to_detail_endpoint(self):
        if hasattr(self, 'lookup_url_kwarg'):
            lookup = self.lookup_url_kwarg or self.lookup_field
        return lookup and lookup in self.kwargs


class PaginateByMaxMixin:

    def get_page_size(self, request):
        if self.page_size_query_param and self.max_page_size and request.query_params.get(self.page_size_query_param) == 'max':
            return self.max_page_size
        return super().get_page_size(request)


# class ReadOnlyCacheResponseAndETAGMixin(ReadOnlyETAGMixin, CacheResponseMixin):
#     pass


# class CacheResponseAndETAGMixin(ETAGMixin, CacheResponseMixin):
#     pass


class NestedViewSetMixin:
    """
    Adds filtering in get_page_size based on .parent_lookup_map definitions.

    Raises:
        Http404: If queryset.filter() raised ValueError.
            This happens if filter string was wrong.
    """

    def get_queryset(self):
        return self.filter_queryset_by_parents_lookups(
            super().get_queryset()
        )

    def filter_queryset(self, queryset):
        queryset = self.filter_queryset_by_parents_lookups(queryset)
        return super().filter_queryset(queryset)

    def filter_queryset_by_parents_lookups(self, queryset):
        """
        Filter queryset using parent_lookup_map
        """
        map_ = getattr(self, 'parent_lookup_map', {})
        filters = self.get_parents_query_dict() # TODO: replace with {} when call is removed
        for kw, filter_ in map_.items():
            if callable(filter_):
                filter_ = filter_()
            filter_ = force_str(filter_).replace('.', '__')
            value = self.kwargs.get(kw, None)
            if value is not None:
                filters[filter_] = value
        if filters:
            try:
                return queryset.filter(**filters)
            except (ValueError, FieldError):
                logger.exception("queryset filtering with parent_lookup_map failed")
                raise Http404
        else:
            return queryset

    def get_parents_query_dict(self):
        """
        Resolve legacy parent query dict.
        Deprecated in the development version. Warning is raised in NestedRouterItem if this feature is used.
        """
        result = {}
        for kwarg_name, kwarg_value in self.kwargs.items():
            if kwarg_name.startswith(extensions_api_settings.DEFAULT_PARENT_LOOKUP_KWARG_NAME_PREFIX):
                query_lookup = kwarg_name.replace(
                    extensions_api_settings.DEFAULT_PARENT_LOOKUP_KWARG_NAME_PREFIX,
                    '',
                    1
                )
                query_value = kwarg_value
                result[query_lookup] = query_value
        return result
