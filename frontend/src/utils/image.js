/**
 * 图片压缩：长边压到 maxSide、JPEG 输出。
 * 手机原图 3~8MB 直接上传会让免费识别模型更容易撞超时，压缩后体积约 1/10。
 * 传入 Blob（File 是其子类）或 dataURL 均可，返回压缩后的 Blob。
 */
export async function compressImage(source, maxSide = 1600, quality = 0.85) {
  const needRevoke = source instanceof Blob
  const url = needRevoke ? URL.createObjectURL(source) : source
  try {
    const img = await new Promise((resolve, reject) => {
      const el = new Image()
      el.onload = () => resolve(el)
      el.onerror = () => reject(new Error('图片读取失败'))
      el.src = url
    })
    const scale = Math.min(1, maxSide / Math.max(img.naturalWidth, img.naturalHeight))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(img.naturalWidth * scale)
    canvas.height = Math.round(img.naturalHeight * scale)
    canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality))
    if (!blob) throw new Error('图片压缩失败')
    return blob
  } finally {
    if (needRevoke) URL.revokeObjectURL(url)
  }
}
