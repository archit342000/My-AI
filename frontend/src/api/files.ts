import { ApiError } from './client';
import type { UploadedFile } from './completions';

interface UploadResponse {
  success: boolean;
  file_id: string;
  original_filename: string;
  mime_type: string;
  file_size: number;
}

/** Uploads one file for a chat with progress (XHR, since fetch has no upload progress). */
export function uploadFile(file: File, chatId: string, onProgress?: (fraction: number) => void): Promise<UploadedFile> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append('file', file);
    form.append('chat_id', chatId);
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/files/upload');
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* non-JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        const r = body as UploadResponse;
        resolve({ file_id: r.file_id, name: r.original_filename, size: r.file_size, mime_type: r.mime_type });
      } else {
        const message = (body as { error?: string } | null)?.error ?? `Upload failed (${xhr.status})`;
        reject(new ApiError(xhr.status, body, message));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, null, 'Network error during upload'));
    xhr.send(form);
  });
}

export function fileUrl(fileId: string): string {
  return `/api/files/${encodeURIComponent(fileId)}`;
}
