from __future__ import print_function
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()
from builtins import range
from io import open
import os
import pdb
import random
from future.moves.urllib.parse import urlparse
from subprocess import PIPE, Popen, check_call

from . import paths
from . import tarrecords


def test_curl_write(self, location):
    """Test whether we can write to a location using curl."""
    proc = Popen(["curl", "--fail", "-s", "-T", "-", location], stdin=PIPE)
    proc.stdin.close()
    if proc.wait() != 0:
        raise Exception("{}: cannot write location".format(location))
    check_call(["curl", "--fail", "-X", "DELETE", location])

# Python 3 os.popen() only has mode = "r" or "w"
# Python 2 code was using default mode as "rb"; changing it to only "r"
def gopen(url, mode="r"):
    """Open the given URL. Supports unusual schemes and uses subprocesses."""
    parsed = urlparse(url)
    if parsed.scheme == "gs":
        if mode[0]=="r":
            return Popen("gsutil cat '%s'" % url, stdout=PIPE, stderr=PIPE, shell=True)
        elif mode[0]=="w":
            return Popen("gsutil cp - '%s'" % url, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True)
        else:
            raise ValueError("{}: unknown mode".format(mode))
    elif parsed.scheme in "http https ftp".split():
        if mode[0]=="r":
            cmd = "curl --fail -s '%s'" % url
            return Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        elif mode[0]=="w":
            test_curl_write(url)
            cmd = "curl --fail -s -T - '%s'" % url
            return Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True)
        else:
            raise ValueError("{}: unknown mode".format(mode))
    elif parsed.scheme in ["", "file"]:
        if mode[0]=="r":
            return open(parsed.path, "rb")
        elif mode[0]=="w":
            return open(parsed.path, "wb")
        else:
            raise ValueError("{}: unknown mode".format(mode))

def test_url(url, size=17):
    """Test whether the given URL is accessible."""
    try:
        with gopen(url) as stream:
            pdb.set_trace()
            data = stream.communicate()[0][:size]
        if len(data) == size:
            return True
        return False
    except Exception as e:
        print(e)
        return False

def test_shards(url, size=17, complete=False):
    """Test whether the shard spec is accessible."""
    shards = list(paths.path_shards(url))
    if complete:
        return all(test_url(s, size=size) for s in shards)
    else:
        return test_url(shards[0], size=size)

def find_shards(urls, size=17, complete=False):
    """Given a list of shard URLs, find the first one that exists."""
    for url in urls:
        pdb.set_trace()
        if test_shards(url, size=size, complete=False):
            return url

def sharditerator(url, epochs=1000000, shuffle=True, **kw):
    """Iterate over sharded tar records."""
    shards = list(paths.path_shards(url))
    for epoch in range(epochs):
        if shuffle: random.shuffle(shards)
        for shard in shards:
            with gopen(shard) as stream:
                for sample in tarrecords.tariterator(stream, **kw):
                    yield sample

def sharditerator_multi(url, epochs=1000000, shuffle=True, multi=1, **kw):
    """Iterate over sharded tar records, opening multiple shards in parallel."""
    assert multi==1, "multi>1 is unimplemented" # FIXME
    shards = list(paths.path_shards(url))
    for epoch in range(epochs):
        if shuffle: random.shuffle(shards)
        for shard in shards:
            with gopen(shard) as stream:
                for sample in tarrecords.tariterator(stream, **kw):
                    yield sample

def sharditerator_once(url, **kw):
    """Iterate over sharded tar records (no shuffling, one epoch only)."""
    return sharditerator(url, epochs=1, shuffle=False, **kw)

def open_source(url, decode=True):
    parsed = urlparse(url)
    if parsed.scheme and len(parsed.scheme)>0 and parsed.scheme[0] == "z":
        from . import zcom
        return list(zcom.Connection(url, codec=decode).items())
    else:
        return sharditerator(url, decode=decode, source=url)

def open_sink(url, encode=True):
    parsed = urlparse(url)
    if parsed.scheme and len(parsed.scheme)>0 and parsed.scheme[0] == "z":
        from . import zcom
        return zcom.Connection(url, codec=encode)
    else:
        stream = gopen(url, "wb")
        return tarrecords.TarWriter(stream, encode=encode)
