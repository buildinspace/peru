#! /bin/bash

set -e

repo_root=$(realpath $(dirname $BASH_SOURCE))

# create a git repo under /tmp with two versions of a text file
lib_repo=`mktemp -d`
echo lib repo $lib_repo
cd $lib_repo
git init -q
echo hi v1 > libfile
git add libfile
git commit -qam "libfile v1"
echo hi v2 > libfile
git commit -qam "libfile v2"

# create a peru project that references that git repo
exe_repo=`mktemp -d`
echo exe repo $exe_repo
cd $exe_repo
cat << END > peru
git_module(
    name = "lib",
    url = "$lib_repo",
    dest = "lib_dest",
    rev = "master",
)
END

# invoke peru to pull in the libfile
$repo_root/peru
if [ "$(cat lib_dest/libfile)" != "hi v2" ] ; then
  echo "Test failed line $LINENO: libfile doesn't match."
  exit 1
fi

# point to master^ and confirm that we get the previous version of libfile
sed -i "s/master/master^/" peru
$repo_root/peru
if [ "$(cat lib_dest/libfile)" != "hi v1" ] ; then
  echo "Test failed line $LINENO: libfile doesn't match."
  exit 1
fi

echo Tests passed.
