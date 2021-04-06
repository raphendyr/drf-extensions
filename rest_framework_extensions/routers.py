# -*- coding: utf-8 -*-
import warnings
from django.utils.functional import cached_property

from rest_framework.routers import (
    DefaultRouter,
    SimpleRouter,
)
from rest_framework_extensions.utils import compose_parent_pk_kwarg_name


class LegacyNestedRegistryItem:
    def __init__(self, router, parent_prefix, parent_item=None, parent_viewset=None):
        self.router = router
        self.parent_prefix = parent_prefix
        self.parent_item = parent_item
        self.parent_viewset = parent_viewset

    def register(self, prefix, viewset, basename, parents_query_lookups):
        self.router._register(
            prefix=self.get_prefix(
                current_prefix=prefix,
                parents_query_lookups=parents_query_lookups),
            viewset=viewset,
            basename=basename,
        )
        return LegacyNestedRegistryItem(
            router=self.router,
            parent_prefix=prefix,
            parent_item=self,
            parent_viewset=viewset
        )

    def get_prefix(self, current_prefix, parents_query_lookups):
        return '{0}/{1}'.format(
            self.get_parent_prefix(parents_query_lookups),
            current_prefix
        )

    def get_parent_prefix(self, parents_query_lookups):
        prefix = '/'
        current_item = self
        i = len(parents_query_lookups) - 1
        while current_item:
            parent_lookup_value_regex = getattr(
                current_item.parent_viewset, 'lookup_value_regex', '[^/.]+')
            prefix = '{parent_prefix}/(?P<{parent_pk_kwarg_name}>{parent_lookup_value_regex})/{prefix}'.format(
                parent_prefix=current_item.parent_prefix,
                parent_pk_kwarg_name=compose_parent_pk_kwarg_name(
                    parents_query_lookups[i]),
                parent_lookup_value_regex=parent_lookup_value_regex,
                prefix=prefix
            )
            i -= 1
            current_item = current_item.parent_item
        return prefix.strip('/')


class NestedRegistryItem:
    def __init__(self, router, prefix, viewset, extra_kwargs=None, parent_item=None):
        self.router = router
        self.prefix = prefix
        self.viewset = viewset
        self.extra_kwargs = extra_kwargs or {}
        self.parent_item = parent_item
        self.parent_pattern = parent_item.full_pattern if parent_item else ''

        self.__register()

    def __register(self):
        # Check that same lookup_url_kwarg is not used twice in same nested chain
        lookup_url_kwarg = self.lookup_url_kwarg
        current = self.parent_item
        while current:
            assert current.lookup_url_kwarg != lookup_url_kwarg, (
                "Viewsets %r and %r are nested and they have same "
                "lookup_url_kwarg %r. Recheck values of lookup_url_kwarg "
                "and lookup_field in those viewsets."
                % (current.viewset, self.viewset, lookup_url_kwarg)
            )
            current = current.parent_item

        prefix = '{0}/{1}'.format(self.parent_pattern, self.prefix).strip('/')
        self.router._register(prefix, self.viewset, **self.extra_kwargs)

    def register(self, prefix, viewset, basename=None, parents_query_lookups=None, **kwargs):
        # support passing as positional argument
        kwargs['basename'] = basename

        # support legacy interface.
        if parents_query_lookups:
            warnings.warn(
                "Usage of `parents_query_lookups` for nested routes is "
                "pending deprecation."
                "Use `parent_lookup_map` in view class instead.",
                PendingDeprecationWarning
            )
            def iter_from(cur):
                while cur is not None:
                    yield cur
                    cur = cur.parent_item
            prev_legacy_item = None
            for item in reversed(list(iter_from(self))):
                legacy_item = LegacyNestedRegistryItem(
                     router=item.router,
                     parent_prefix=item.prefix,
                     parent_viewset=item.viewset,
                     parent_item=prev_legacy_item,
                )
                prev_legacy_item = legacy_item
            return legacy_item.register(
                prefix=prefix,
                viewset=viewset,
                parents_query_lookups=parents_query_lookups,
                **kwargs)

        return NestedRegistryItem(
            router=self.router,
            prefix=prefix,
            viewset=viewset,
            extra_kwargs=kwargs,
            parent_item=self,
        )

    @cached_property
    def lookup_url_kwarg(self):
        return (
            getattr(self.viewset, 'lookup_url_kwarg', None) or
            getattr(self.viewset, 'lookup_field', None) or
            'ok'
        )

    @cached_property
    def full_pattern(self):
        lookup_value_regex = getattr(self.viewset, 'lookup_value_regex', '[^/.]+')
        lookup_url_kwarg = self.lookup_url_kwarg

        return '{parent_pattern}/{prefix}/(?P<{lookup_url_kwarg}>{lookup_value_regex})'.format(
            parent_pattern=self.parent_pattern,
            prefix=self.prefix,
            lookup_url_kwarg=lookup_url_kwarg,
            lookup_value_regex=lookup_value_regex,
        ).strip('/')

    def __enter__(self):
        """
        Support with statement

        Example:
            with api.register(r'example', ExampleViewSet) as example:
                example.register(r'nested', NestedBiewSet)
        """
        return self

    def __exit__(self, type, value, traceback):
        pass


class NestedRouterMixin:
    def _register(self, *args, **kwargs):
        return super().register(*args, **kwargs)

    def register(self, prefix, viewset, basename=None, **kwargs):
        kwargs['basename'] = basename
        return NestedRegistryItem(
            router=self,
            prefix=prefix,
            viewset=viewset,
            extra_kwargs=kwargs
        )


class ExtendedRouterMixin(NestedRouterMixin):
    pass


class ExtendedSimpleRouter(ExtendedRouterMixin, SimpleRouter):
    pass


class ExtendedDefaultRouter(ExtendedRouterMixin, DefaultRouter):
    pass
