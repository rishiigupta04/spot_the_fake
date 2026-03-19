const rawBaseUrl = (import.meta.env.VITE_API_BASE_URL || '').trim()

// Empty base means "same origin", useful when frontend and backend are behind one host.
const normalizedBaseUrl = rawBaseUrl.replace(/\/+$/, '')

export const buildApiUrl = (path = '/') => {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return normalizedBaseUrl ? `${normalizedBaseUrl}${normalizedPath}` : normalizedPath
}

export const buildStaticAssetUrl = (folder, fileName) => {
  if (!fileName) return null
  return buildApiUrl(`/static/${folder}/${encodeURIComponent(fileName)}`)
}

export const postSimilarityUpload = (axiosClient, file) => {
  const formData = new FormData()
  formData.append('file', file)

  return axiosClient.post(buildApiUrl('/similarity-upload'), formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}