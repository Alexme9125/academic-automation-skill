"""Small real PDFs generated with stdlib, including a correct xref table."""
def pdf_bytes(text=''):
    stream = ('BT /F1 12 Tf 30 100 Td (' + text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)') + ') Tj ET').encode('ascii') if text else b''
    objects = [b'<</Type /Catalog /Pages 2 0 R>>', b'<</Type /Pages /Kids [3 0 R] /Count 1>>',
               b'<</Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources <</Font <</F1 5 0 R>>>> /Contents 4 0 R>>',
               b'<</Length ' + str(len(stream)).encode() + b'>>\nstream\n' + stream + b'\nendstream',
               b'<</Type /Font /Subtype /Type1 /BaseFont /Helvetica>>']
    data = bytearray(b'%PDF-1.4\n'); offsets = [0]
    for n, obj in enumerate(objects, 1):
        offsets.append(len(data)); data.extend(str(n).encode() + b' 0 obj\n' + obj + b'\nendobj\n')
    xref = len(data)
    data.extend(b'xref\n0 6\n0000000000 65535 f \n')
    for offset in offsets[1:]: data.extend(('%010d 00000 n \n' % offset).encode())
    data.extend(b'trailer\n<</Size 6 /Root 1 0 R>>\nstartxref\n' + str(xref).encode() + b'\n%%EOF\n')
    return bytes(data)

PDF = pdf_bytes()
