# Using peru with make

*[Editor's node: The dude who wrote this doesn't actually know very much
about make. If he screwed anything up, please file a bug!]*

Getting peru and make to play nicely together can be a little tricky.
Here are a few examples, going roughly from the simplest to the most
correct.

For these examples, we'll pretend that we want to fetch a Hello World C
program, compile it, and run it. The
[leachim6/hello-world](https://github.com/leachim6/hello-world) project
offers a Hello World example in every language, so we'll get our code
from there. Here's the `peru.yaml` file to fetch just their C example
(`c.c`) into the root of our project

```yaml
imports:
    helloworld: ./

git module helloworld:
    url: https://github.com/leachim6/hello-world
    pick: c/c.c
    export: c/
```

And here's a simple `Makefile` to get us started:

```make
run: hello
	./hello

hello: peru
	gcc -o hello c.c

peru:
	peru sync
```

Because the `peru` target doesn't produce a file called `peru`, make
will run it every time. That's both good and bad. It's good because if
you ever use the `peru override` command, make isn't going to have any
idea when your overrides have changed, so running `peru sync` on every
build is the only way to get overrides right. But it's bad because now
make is going to run the `hello` target every time too, even if the C
file hasn't changed. It's not such a big deal for just one C file, but
if we were building a project that took a long time, it would be
annoying. Here's one way to fix that problem:

```make
run: hello
	./hello

hello: .peru/lastimports
	gcc -o hello c.c

.peru/lastimports: peru.yaml
	peru sync
```

Here `gcc` will only run when the imports have changed. We make this
work by referring to the `lastimports` file that peru generates. That
file contains the git hash of all the files peru has put on disk, and
importantly, peru promises not to touch that file when the hash hasn't
changed.

That's what we want for `gcc`. What about for `peru sync`? Because we
threw in the explicit dependency on `peru.yaml`, make will kindly rerun
the sync for us if we change the YAML file. If you don't use overrides,
that might be all you need. But if you do use overrides, you'll need an
extra hack:

```make
run: hello
	./hello

hello: .peru/lastimports
	gcc -o hello c.c

.peru/lastimports: phony
	peru sync

phony:
```

This is similar to the last example, in that `gcc` only runs when the
imported files actually change. But we've added a phony target, which
produces no files. Depending on that forces make to run the `peru sync`
rule every time, so overrides will work properly. A `peru sync` with
everything in cache amounts to a single `git status`, so you shouldn't
notice a slowdown unless your dependencies are extremely large.

The `Makefile` in this directory reproduces the last example, with some
comments and a real `.PHONY` declaration (which keeps make from getting
confused if we ever do create a file called "phony" for some reason).
