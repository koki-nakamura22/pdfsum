"""digestkit との接合層 (Source / Sink のカスタム実装)."""
from pdfsum.digest.sink import PdfsumSink
from pdfsum.digest.source import SingleFileSource

__all__ = ["PdfsumSink", "SingleFileSource"]
