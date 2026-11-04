// Cliente de la API.
export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export async function api(method, path, body) {
  let response;
  try {
    response = await fetch(path, {
      method,
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'precimec' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, 'No se pudo conectar con el servidor.');
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(response.status, data.error || 'Ocurrió un error inesperado.');
  return data;
}

// La carga usa XHR porque fetch no informa el avance de la subida.
export function uploadFile(file, { replaceId, onProgress } = {}) {
  const base = replaceId ? `/api/admin/assets/${replaceId}/replace` : '/api/admin/assets';
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${base}?filename=${encodeURIComponent(file.name)}`);
    xhr.setRequestHeader('X-Requested-With', 'precimec');
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      let data = {};
      try { data = JSON.parse(xhr.responseText); } catch { /* respuesta sin JSON */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data);
      else reject(new ApiError(xhr.status, data.error || 'No se pudo cargar el archivo.'));
    };
    xhr.onerror = () => reject(new ApiError(0, 'La carga se interrumpió. Revisa el tamaño y el formato del archivo.'));
    xhr.send(file);
  });
}
