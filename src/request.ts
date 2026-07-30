import { URLExt } from '@jupyterlab/coreutils';

import { ServerConnection } from '@jupyterlab/services';
import { IEquationInput, IEquationRecord } from './types';

/**
 * Call the server extension
 *
 * @param endPoint API REST end point for the extension
 * @param serverSettings The server settings to use for the request
 * @param init Initial values for the request
 * @returns The response body interpreted as JSON
 */
export async function requestAPI<T>(
  endPoint: string,
  serverSettings: ServerConnection.ISettings,
  init: RequestInit = {}
): Promise<T> {
  // Make request to Jupyter API
  const requestUrl = URLExt.join(
    serverSettings.baseUrl,
    'api',
    'jupyterlab-sympy-assistant', // our server extension's API namespace
    endPoint
  );

  let response: Response;
  try {
    response = await ServerConnection.makeRequest(
      requestUrl,
      init,
      serverSettings
    );
  } catch (error) {
    throw new ServerConnection.NetworkError(error as any);
  }

  let data: any = await response.text();

  if (data.length > 0) {
    try {
      data = JSON.parse(data);
    } catch (error) {
      console.log('Not a JSON response body.', response);
    }
  }

  if (!response.ok) {
    const isHtml =
      typeof data === 'string' &&
      data.replace(/^\s+/, '').startsWith('<!DOCTYPE');
    const message = isHtml
      ? `Server returned HTML for ${requestUrl} (HTTP ${response.status}). Check Jupyter server logs for this request.`
      : data.message || data.error || JSON.stringify(data);
    throw new ServerConnection.ResponseError(response, message);
  }

  return data;
}

export class EquationLibraryApi {
  constructor(private serverSettings: ServerConnection.ISettings) {}

  async list(): Promise<IEquationRecord[]> {
    const payload = await requestAPI<{ equations: IEquationRecord[] }>(
      'equations',
      this.serverSettings
    );
    return payload.equations;
  }

  async create(input: IEquationInput): Promise<IEquationRecord> {
    const payload = await requestAPI<{ equation: IEquationRecord }>(
      'equations',
      this.serverSettings,
      {
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
        method: 'POST'
      }
    );
    return payload.equation;
  }

  async update(
    id: string,
    input: Partial<IEquationInput>
  ): Promise<IEquationRecord> {
    const payload = await requestAPI<{ equation: IEquationRecord }>(
      `equations/${encodeURIComponent(id)}`,
      this.serverSettings,
      {
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
        method: 'PUT'
      }
    );
    return payload.equation;
  }

  async remove(id: string): Promise<void> {
    await requestAPI<void>(
      `equations/${encodeURIComponent(id)}`,
      this.serverSettings,
      {
        method: 'DELETE'
      }
    );
  }
}
