import { describe, expect, it } from 'vitest'
import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js'
import worker from '../src/index.js'

describe('MCP Worker', () => {
  it('initializes, lists tools, and calls greeting and time tools through MCP', async () => {
    const transport = new StreamableHTTPClientTransport(new URL('http://localhost/mcp'), {
      fetch: async (input, init) => worker.fetch(new Request(input, init)),
    })
    const client = new Client({ name: 'worker-test', version: '1.0.0' })
    await client.connect(transport)
    try {
      const { tools } = await client.listTools()
      expect(tools.map(tool => tool.name).sort()).toEqual(['getCurrentTime', 'sayHello'])
      const greeting = await client.callTool({ name: 'sayHello', arguments: { name: 'Ada' } })
      expect(greeting.isError).not.toBe(true)
      expect(greeting.content).toEqual([{ type: 'text', text: 'Hello from an MCP Worker, Ada!' }])
      const time = await client.callTool({ name: 'getCurrentTime', arguments: {} })
      expect(time.isError).not.toBe(true)
      expect(time.content).toEqual([{ type: 'text', text: expect.stringMatching(/^\d{4}-\d{2}-\d{2}T/) }])
      const invalid = await client.callTool({ name: 'sayHello', arguments: {} })
      expect(invalid.isError).toBe(true)
    } finally {
      await client.close()
    }
  })

  it('returns 404 for paths outside the MCP endpoint', async () => {
    expect((await worker.fetch(new Request('http://localhost/'))).status).toBe(404)
  })
})
