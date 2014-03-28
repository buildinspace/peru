#! /bin/bash

set -e

repo_root=$(realpath $(dirname $BASH_SOURCE))

# keep our temp files from cluttering /tmp
export TMPDIR=/tmp/perutest
mkdir -p $TMPDIR

fail() {
  # print the line where fail() is called, followed by arguments
  echo
  echo Error line ${BASH_LINENO[$((${#BASH_LINENO[@]} - 2))]}: $*
  exit 1
}

run_peru() {
  $repo_root/main.py
}

# Shim git in the $PATH so that all calls are logged.
shim_dir=`mktemp -d`
git_log=`mktemp`
cat << END > $shim_dir/git
#! /bin/bash
echo \$0 \$* >> $git_log
$(which git) "\$@"
END
chmod 755 $shim_dir/git
export PATH=$shim_dir:$PATH

# create a git repo under /tmp with some files
lib_repo=`mktemp -d`
cd $lib_repo
git init -q
echo hi v1 > libfile
mkdir subdir
echo stuff > subdir/subfile
git add -A
git commit -qam "libfile v1"
first_commit=`git rev-parse HEAD`
echo hi v2 > libfile
git commit -qam "libfile v2"
second_commit=`git rev-parse HEAD`

# create a peru project that references that git repo
exe_repo=`mktemp -d`
cd $exe_repo
write_peru_file_at_rev() {
  cat << END > $exe_repo/peru
imports:
    lib: lib_dest/
    pathlib: path_lib_dest/

module lib:
    type: git
    url: $lib_repo
    rev: $1
    default_rule: builtfile

    rule builtfile:
        #build: echo built stuff > builtfile
        #export: subdir/

# Reference the same repo through the path plugin, to test that too.
module pathlib:
    type: path
    path: $lib_repo
END
}
write_peru_file_at_rev $first_commit

echo git log $git_log
echo lib path $lib_repo
echo exe path $exe_repo

# invoke peru to pull in the first commit
run_peru
if [ "$(cat lib_dest/libfile)" != "hi v1" ] ; then
  fail "libfile doesn't match -- is anything working?!"
fi

# make sure the path rule was pulled in too
if [ "$(cat path_lib_dest/libfile)" != "hi v2" ] ; then
  fail "libfile doesn't match in the path module"
fi

# uncomment the build command and confirm it gets built
sed -i 's/#build/build/' $exe_repo/peru
run_peru
if [ "$(cat lib_dest/builtfile)" != "built stuff" ] ; then
  fail "builtfile didn't get built"
fi

# uncomment the export field and check that subfile ends up in lib_dest
sed -i 's/#export/export/' $exe_repo/peru
run_peru
if [ "$(cat lib_dest/subfile)" != "stuff" ] ; then
  fail "the export field didn't work"
fi

# point to the second commit and confirm that we get it
write_peru_file_at_rev $second_commit
run_peru
if [ "$(cat lib_dest/libfile)" != "hi v2" ] ; then
  fail "libfile doesn't match"
fi

# we shouldn't have done any fetches by this point
num_fetches=`grep fetch $git_log | wc -l`
if [ $num_fetches != 0 ] ; then
  fail expected 0 fetches, found $num_fetches in $git_log
fi

# add a new commit to the lib repo
cd $lib_repo
echo hi v3 > libfile
git commit -qam "libfile 3"
third_commit=`git rev-parse HEAD`
cd $exe_repo

# Use peru to get the new version. This should cause a fetch.
write_peru_file_at_rev $third_commit
run_peru
if [ "$(cat lib_dest/libfile)" != "hi v3" ] ; then
  fail "libfile doesn't match"
fi
num_fetches=`grep fetch $git_log | wc -l`
if [ $num_fetches != 1 ] ; then
  fail expected 1 fetch, found $num_fetches in $git_log
fi

# Point to master and run peru again, which should cause another fetch.
write_peru_file_at_rev master
run_peru
num_fetches=`grep fetch $git_log | wc -l`
if [ $num_fetches != 2 ] ; then
  fail expected 2 fetches, found $num_fetches in $git_log
fi

echo All tests passed.
