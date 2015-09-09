# Declaring phony targets explicitly in your Makefiles is a good habit. If for
# some strange reason we created a file called "run" or "phony", make could get
# tricked into thinking that those rules didn't need to run. This directive
# means that make will never look for those file.
.PHONY: run phony

run: hello
	./hello

hello: .peru/lastimports
	gcc -o hello c.c

# Depending on a phony target causes this rule to run every time it's used.
# This is what we want -- it ensures that peru will check local overrides for
# any changes. But the lastimports file will only be touched if the imports
# tree actually changes, so the gcc rule above doesn't run every time.
.peru/lastimports: phony
	peru sync

phony:
