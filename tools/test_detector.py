import numpy as np, tensorflow as tf, glob
from PIL import Image
labels = ['huf_500','huf_1000','huf_2000','huf_5000','huf_10000','huf_20000']
it = tf.lite.Interpreter(model_path=r'..\app\src\main\assets\huf_banknote_detector.tflite')
it.allocate_tensors()
inp = it.get_input_details()[0]
out = it.get_output_details()[0]

def predict(path):
    img = Image.open(path).convert('RGB').resize((640,640))
    a = np.array(img).astype(np.float32)[None, ...] / 255.0
    it.set_tensor(inp['index'], a)
    it.invoke()
    o = it.get_tensor(out['index'])[0]
    cls = o[4:10, :]
    ba = cls.max(axis=0).argmax()
    bc = int(cls[:, ba].argmax())
    conf = float(cls[:, ba].max())
    return labels[bc], conf

for denom in ['500', '2000', '10000']:
    print('=== huf_' + denom + ' kepek ===')
    for p in glob.glob('banknote_yolo/images/test/huf_' + denom + '__*.jpg')[:4]:
        lab, cf = predict(p)
        mark = 'OK' if lab == ('huf_' + denom) else 'HIBA'
        print('  ' + lab.ljust(10) + ' conf ' + format(cf, '.3f') + '  ' + mark)
