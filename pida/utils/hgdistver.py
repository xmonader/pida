import os
import sys
import subprocess
def getoutput(cmd, cwd='.'):
    p = subprocess.Popen(cmd,
                         shell=True,
                         stdout=subprocess.PIPE,
                         cwd=cwd,
                        )
    out, _ = p.communicate()
    return out.decode() # will kill us sometimes


def hg(args, cwd='.'):
    return getoutput('hg ' + args, cwd).strip()

def version_from_cachefile(root, cachefile=None):
    #XXX: for now we ignore root
    if not cachefile:
        return
    #replaces 'with open()' from py2.6
    fd = open(cachefile)
    fd.readline()  # remove the comment
    version = None
    try:
        line = fd.readline()
        version_string = line.split(' = ')[1].strip()
        version = version_string[1:-1]
    except:  # any error means invalid cachefile
        pass
    fd.close()
    return version


def version_from_hg_id(root, cachefile=None):
    """stolen logic from mercurials setup.py as well"""
    l = hg('id -i -t', root).split()
    node = l.pop(0)
    for tag in l:
        #XXX: find better guess if version-number logic
        if tag[0].isdigit():
            version = tag
            if node[-1] == '+':  # propagate the dirty status to the tag
                version += '+'
            return version


def version_from_hg15_parents(root, cachefile=None):
    node = hg('id -i', root)
    if node.strip('+') == '000000000000':
        return '0.0.dev0-' + node

    cmd = 'parents --template "{latesttag} {latesttagdistance}"'
    out = hg(cmd, root)
    try:
        tag, dist = out.split()
        if tag == 'null':
            tag = '0.0'
        return '%s.dev%s-%s' % (tag, dist, node)
    except ValueError:
        pass  # unpacking failed, old hg


def version_from_hg_log_with_tags(root, cachefile=None):
    #NOTE: this is only a fallback called from version_from_hg15_parents
    node = hg('id -i', root)
    cmd = r'hg log -r %s:0 --template "{tags} \n"'
    cmd = cmd % node.rstrip('+')
    proc = subprocess.Popen(cmd,
                            cwd=root,
                            shell=True,
                            stdout=subprocess.PIPE,
                           )
    dist = -1  # no revs vs one rev is tricky

    for dist, line in enumerate(proc.stdout):
        line = line.decode()
        tags = [t for t in line.split() if not t.isalpha()]
        if tags:
            return '%s.dev%s-%s' % (tags[0], dist, node)

    return  '0.0.dev%s-%s' % (dist + 1, node)


def version_from_hg(root, cachefile=None):
    # no .hg means no way to get it
    if not os.path.isdir(os.path.join(root, '.hg')):
        return
    # if id has a tag we are lucky
    version_from_id = version_from_hg_id(root)
    if version_from_id:
        return version_from_id
    hgver_out = hg('--version')
    hgver_out = hgver_out.splitlines()[0].rstrip(')')
    hgver = hgver_out.split('version ')[-1]
    if hgver < '1.5':
        return version_from_hg_log_with_tags(root)
    else:
        return version_from_hg15_parents(root)

def _archival_to_version(data):
    """stolen logic from mercurials setup.py"""
    if 'tag' in data:
        return data['tag']
    elif 'latesttag' in data:
        return '%(latesttag)s.dev%(latesttagdistance)s-%(node).12s' % data
    else:
        return data.get('node', '')[:12]


def _data_from_archival(path):
    import email
    data = email.message_from_file(open(str(path)))
    return dict(data.items())


def version_from_archival(root, cachefile=None):
    for parent in root, os.path.dirname(root):
        archival = os.path.join(parent, '.hg_archival.txt')
        if os.path.exists(archival):
            data = _data_from_archival(archival)
            return _archival_to_version(data)


def version_from_sdist_pkginfo(root, cachefile=None):
    pkginfo = os.path.join(root, 'PKG-INFO')
    if cachefile is None and os.path.exists(pkginfo):
        data = _data_from_archival(pkginfo)
        version = data.get('Version')
        if version != 'UNKNOWN':
            return version


def write_cachefile(path, version):
    fd = open(path, 'w')
    try:
        fd.write('# this file is autogenerated by hgdistver + setup.py\n')
        fd.write('version = %r' % version)
    finally:
        fd.close()


methods = [
    version_from_hg,
    version_from_cachefile,
    version_from_sdist_pkginfo,
    version_from_archival,
]


def get_version(cachefile=None, root=None):
    if root is None:
        root = os.getcwd()
    if cachefile is not None:
        cachefile = os.path.join(root, cachefile)
    try:
        version = None
        for method in methods:
            version = method(root=root, cachefile=cachefile)
            if version:
                if version.endswith('+'):
                    import time
                    version += time.strftime('%Y%m%d')
                return version
    finally:
        if cachefile and version:
            write_cachefile(cachefile, version)


if __name__ == '__main__':
    print('Guessed Version %s' % (get_version(),))
