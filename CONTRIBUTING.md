# Contributing

We always like contributions here in `peru`!

First of all, if you're looking for something to work or you have some idea for a new feature or you found a bug, then check out our [issue tracker](https://github.com/buildinspace/peru/issues) for this.

In the issue, discuss your idea and implementation.

Then if you want to make a contribution to `peru` then please raise a
[Pull Request](https://github.com/buildinspace/peru/pulls) on GitHub.

To help speed up the review process please ensure the following:

- The PR addresses an open issue.
- The project passes linting with `make check` or `flake8 peru tests`.
- All tests are passing locally with (includes linting): `make test` or `python test.py`.
- If adding a new feature you also add documentation.

## Developing

The minimal Python version supported is 3.5. If you are developing in newer versions, be aware of functions not backwards compatible. The Github Workflow will make this check in the pull request.

To check out a local copy of the project you can [fork the project on GitHub](https://github.com/buildinspace/peru/fork)
and then clone it locally. If you are using https, then you should adapt to it.

```bash
git clone git@github.com:yourusername/peru.git
cd peru
```

This project uses `flake8` for linting. To configure your local environment, please install these development dependencies.
You may want to do this in a virtualenv; use `make venv` to create it in
`.venv` in the current directory.

```bash
make deps-dev
# OR
pip install -r requirements-dev.txt
```

then you can run `flake8` with

```bash
make check
# OR
flake8 peru tests
```

## Testing

You can check that things are working correctly by calling the tests.

```bash
make test
# OR
python test.py -v
```

```
$ python test.py -v
test_safe_communicate (test_async.AsyncTest) ... ok
test_basic_export (test_cache.CacheTest) ... ok
.
.
.
test_assert_contents (test_test_shared.SharedTestCodeTest) ... ok
test_create_dir (test_test_shared.SharedTestCodeTest) ... ok
test_read_dir (test_test_shared.SharedTestCodeTest) ... ok
----------------------------------------------------------------------
Ran 152 tests in 45.11s

OK (skipped=1)
```

These checks will be run automatically when you make a pull request.

You should always have a skipped test, because this is a platform specific tests.

If you are working on a new feature please add tests to ensure the feature works as expected. If you are working on a bug fix then please add a test to ensure there is no regression.

Tests are stored in `peru/tests` and verify the current implementation to see how your test will fit in.

## Making a Pull Request

Once you have made your changes and are ready to make a Pull Request please ensure tests and linting pass locally before pushing to GitHub.

When making your Pull Request please include a short description of the changes, but more importantly why they are important.

Perhaps by writing a before and after paragraph with user examples.

```
# New feature short description here

Closes #56

**Changes**

This PR includes a new feature that ...

**Before**

If a user tried to pull a repository ...

    ```python
        > code example
        >
    ```
**After**

If a user tries to pull a repository now ...

    ```python
        > code example
        >
    ```
```

After that you should wait the review and perform possible changes in the submitted code.
