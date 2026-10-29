import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js'
import { WebStandardStreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js'
import { z } from 'zod'

function createServer() {
  const server = new McpServer({ name: 'mcp-hello', version: '0.2.0' })
  server.registerTool('sayHello', {
    description: 'Return a greeting.',
    inputSchema: { name: z.string().min(1) },
  }, async ({ name }) => ({
    content: [{ type: 'text', text: `Hello from an MCP Worker, ${name}!` }],
  }))
  server.registerTool('getCurrentTime', {
    description: 'Return the current UTC time with an optional message.',
    inputSchema: { message: z.string().optional() },
  }, async ({ message }) => {
    const timestamp = new Date().toISOString()
    return { content: [{ type: 'text', text: message ? `${message} at ${timestamp}` : timestamp }] }
  })
  return server
}

export default {
  async fetch(request: Request): Promise<Response> {
    if (new URL(request.url).pathname !== '/mcp') {
      return new Response('Not found', { status: 404 })
    }
    const server = createServer()
    const transport = new WebStandardStreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
      enableJsonResponse: true,
    })
    await server.connect(transport)
    try {
      return await transport.handleRequest(request)
    } finally {
      await server.close()
    }
  },
}
