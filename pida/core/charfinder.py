# -*- coding: utf-8 -*- 
# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
"""
    Chartype detection

    :copyright: 2005-2008 by The PIDA Project
    :license: GPL 2 or later (see README/COPYING/LICENSE)
"""


import codecs
import re

class IEncodingDetector:
    def __call__(self, stream, filename, mimetype):
        """Should return None and not found and a string with the
        encoding when it is found."""

#def open_encoded(filename, *args, **kwargs):
#    """Opens and auto detects the encoding"""
#    stream = open(filename, "rb")
#    encoding = find_encoding_stream(stream)
#    stream.seek(0)
#    return codecs.EncodedFile(stream, encoding, *args, **kwargs)



class MimeDetector:
    def __init__(self):
        self.mimes = {}
    
    def register(self, mime, sniffer):
        self.mimes[mime] = sniffer

    def __call__(self, stream, filename, mimetype):
    
        try:
            return self.mimes[mimetype](stream, filename, mimetype)
        except KeyError:
            pass

class DumbDetector:
    encodings = ["utf-8", "iso-8859-15", "windows-1252"]
    
    def __call__(self, stream, filename, mimetype):
        for encoding in self.encodings:
            try:
                codecs.open(filename, encoding=encoding).read()
                return encoding
            except UnicodeDecodeError:
                pass
        return "ascii"
        
class DetectorManager:

    def __init__(self, *args):
        self.detectors = list(args)
        
        self.last_resort = DumbDetector()
    
    def __call__(self, stream, filename, mimetype):
        for encoder in self.detectors:
            encoding = encoder(stream, filename, mimetype)
            stream.seek(0)
            if encoding is not None:
                break
            
        if encoding is None:
            return self.last_resort(stream, filename, mimetype)
        
        return encoding

    def append_detector(self, detector):
        self.detectors.append(detector)
    
    def insert_detector(sef, index, detector):
        self.detectors.insert(index, detector)

##############################################################################
# These are the singletons used so that other programs can register
# XXX: this could be moved later to a plugin.Registry
MIME_DETECTOR = MimeDetector()
DETECTOR_MANAGER = DetectorManager(MIME_DETECTOR)

##############################################################################
# Register a Mime-type sniffer
class PythonDetector:

    PY_ENC = re.compile(r"coding: ([\w\-_0-9]+)")
    
    def _sniff_python_line(self, line):
        return self.PY_ENC.search(line).group(1)

    def __call__(self, stream, filename, mimetype):
        try:
            return self._sniff_python_line(stream.readline())
        except AttributeError:
            pass
        
        try:
            return self._sniff_python_line(stream.readline())
        except AttributeError:
            pass


MIME_DETECTOR.register(("text", "x-python"), PythonDetector())

##############################################################################
# Register chardet, which is an optional detection scheme
try:
    from chardet.universaldetector import UniversalDetector
    
    def chardet_sniff(stream, filename, mimetype):
        detector = UniversalDetector()
        chunk = stream.read(4086)
        while chunk != "":
            detector.feed(chunk)
            if detector.done:
                break
            chunk = stream.read(4086)
            
        detector.close()
        return detector.result["encoding"]
        
    DETECTOR_MANAGER.append_detector(chardet_sniff)
    
except ImportError:
    pass
