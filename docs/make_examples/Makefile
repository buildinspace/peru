# Declaring phony targets explicitly in your Makefiles is a good habit. If for
# some strange reason we created a file called "run" or "phony", make could get
# tricked into thinking that those rules didn't need to run. This directive
# means that make will never look for those files.
.PHONY: run phony

run: hello
	./hello

# Depending on the lastimports file means that this rule will only run when the
# imports actually change, even though the sync runs every time. Peru will not
# touch this file if nothing has changed since the last sync.
hello: .peru/lastimports
	gcc -o hello c.c

# Depending on a phony target causes this rule to run every time it's
# referenced. This is what we want; it ensures that peru will check local
# overrides for any changes, even though make doesn't know about them.
.peru/lastimports: phony
	peru sync

phony:
