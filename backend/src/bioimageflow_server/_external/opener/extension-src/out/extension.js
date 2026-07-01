"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const http = __importStar(require("http"));
const vscode = __importStar(require("vscode"));
const PORT = 60351;
const HOST = '127.0.0.1';
const CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
};
let openQueue = Promise.resolve();
function activate(context) {
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
async function handleRequest(req, res) {
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
    }
    catch (err) {
        console.error('Error in BioImageFlow opener:', err);
        res.writeHead(500, CORS_HEADERS);
        res.end('Error: ' + (err instanceof Error ? err.message : 'Unknown error'));
    }
}
function deactivate() {
}
