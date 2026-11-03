from rapidocr_onnxruntime import RapidOCR
from rapidocr_onnxruntime.ch_ppocr_v3_rec.text_recognize import TextRecognizer
import os
H=os.path.dirname(os.path.abspath(__file__))
def make():
    o=RapidOCR()
    o.text_recognizer=TextRecognizer({'model_path':os.path.join(H,'k_rec.onnx'),'rec_img_shape':[3,48,320],'rec_batch_num':6,'keys_path':os.path.join(H,'k_dict.txt'),'use_cuda':False})
    return o
