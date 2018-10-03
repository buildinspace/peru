from textwrap import dedent

from peru import plugin

import shared


def assert_parallel(n):
    # The plugin module keep a global counter of all the jobs that run in
    # parallel, so that we can write these tests.
    if plugin.DEBUG_PARALLEL_MAX != n:
        raise AssertionError('Expected {} parallel {}. Counted {}.'.format(
            n, 'job' if n == 1 else 'jobs', plugin.DEBUG_PARALLEL_MAX))


class ParallelismTest(shared.PeruTest):
    def setUp(self):
        # Make sure nothing is fishy with the jobs counter, and reset the max.
        plugin.debug_assert_clean_parallel_count()
        plugin.DEBUG_PARALLEL_MAX = 0

    def tearDown(self):
        # Make sure nothing is fishy with the jobs counter. No sense in
        # resetting the max here, because the rest of our tests don't know to
        # reset it anyway.
        plugin.debug_assert_clean_parallel_count()

    def test_two_jobs_in_parallel(self):
        # This just checks that two different modules can actually be fetched
        # in parallel.
        foo = shared.create_dir()
        bar = shared.create_dir()
        peru_yaml = dedent('''\
            imports:
                foo: ./
                bar: ./

            cp module foo:
                path: {}

            cp module bar:
                path: {}
            '''.format(foo, bar))
        test_dir = shared.create_dir({'peru.yaml': peru_yaml})
        shared.run_peru_command(['sync'], test_dir)
        assert_parallel(2)

    def test_jobs_flag(self):
        # This checks that the --jobs flag is respected, even when two modules
        # could have been fetched in parallel.
        foo = shared.create_dir()
        bar = shared.create_dir()
        peru_yaml = dedent('''\
            imports:
                foo: ./
                bar: ./

            cp module foo:
                path: {}

            cp module bar:
                path: {}
            '''.format(foo, bar))
        test_dir = shared.create_dir({'peru.yaml': peru_yaml})
        shared.run_peru_command(['sync', '-j1'], test_dir)
        assert_parallel(1)

    def test_identical_fields(self):
        # This checks that modules with identical fields are not fetched in
        # parallel. This is the same logic that protects us from fetching a
        # given module twice, like when it's imported with two different named
        # rules.
        foo = shared.create_dir()
        peru_yaml = dedent('''\
            imports:
                foo1: ./
                foo2: ./

            cp module foo1:
                path: {}

            cp module foo2:
                path: {}
            '''.format(foo, foo))
        test_dir = shared.create_dir({'peru.yaml': peru_yaml})
        shared.run_peru_command(['sync'], test_dir)
        assert_parallel(1)

    def test_identical_plugin_cache_fields(self):
        # Plugins that use caching also need to avoid running in parallel, if
        # their cache directories are the same. The noop_cache plugin (created
        # for this test) uses the path field (but not the nonce field) in its
        # plugin cache key. Check that these two modules are not fetched in
        # parallel, even though their module fields aren't exactly the same.
        foo = shared.create_dir()
        peru_yaml = dedent('''\
            imports:
                foo1: ./
                foo2: ./

            noop_cache module foo1:
                path: {}
                # nonce is ignored, but it makes foo1 different from foo2 as
                # far as the module cache is concerned
                nonce: '1'

            noop_cache module foo2:
                path: {}
                nonce: '2'
            '''.format(foo, foo))
        test_dir = shared.create_dir({'peru.yaml': peru_yaml})
        shared.run_peru_command(['sync'], test_dir)
        assert_parallel(1)
