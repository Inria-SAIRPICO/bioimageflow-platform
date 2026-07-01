import * as http from 'http';
import * as vscode from 'vscode';

const PORT = 60351;
const HOST = '127.0.0.1';

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

let openQueue: Promise<void> = Promise.resolve();

export function activate(context: vscode.ExtensionContext) {
  const server = http.createServer((req, res) => {
    if (req.method === 'OPTIONS') {
      res.writeHead(200, CORS_HEADERS);
      res.end();
      return;
    }

    const task = () => handleRequest(req, res);
    openQueue = openQueue.then(task, task);
  });

  server.listen(PORT, HOST, () => {
    console.log(`BioImageFlow opener listening on http://${HOST}:${PORT}`);
  });

  context.subscriptions.push({
    dispose: () => server.close(),
  });
}

async function handleRequest(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
  try {
    const url = new URL(req.url || '', `http://${req.headers.host}`);
    if (url.pathname !== '/open') {
      res.writeHead(404, CORS_HEADERS);
      res.end('Not Found');
      return;
    }

    const filePath = url.searchParams.get('path');
    const type = url.searchParams.get('type') || 'file';
    const newWindow = url.searchParams.get('new_window') === 'true';
    if (!filePath) {
      res.writeHead(400, CORS_HEADERS);
      res.end('Missing "path" parameter');
      return;
    }

    const uri = vscode.Uri.file(filePath);
    if (type === 'folder' || type === 'workspace') {
      await vscode.commands.executeCommand('vscode.openFolder', uri, {
        forceNewWindow: newWindow,
      });
      res.writeHead(200, CORS_HEADERS);
      res.end(`Opened ${type}: ${filePath}`);
      return;
    }

    const doc = await vscode.workspace.openTextDocument(uri);
    await vscode.window.showTextDocument(doc);
    res.writeHead(200, CORS_HEADERS);
    res.end(`Opened file: ${filePath}`);
  } catch (err) {
    console.error('Error in BioImageFlow opener:', err);
    res.writeHead(500, CORS_HEADERS);
    res.end('Error: ' + (err instanceof Error ? err.message : 'Unknown error'));
  }
}

export function deactivate() {
  // Cleanup is handled by the subscription registered in activate().
}
