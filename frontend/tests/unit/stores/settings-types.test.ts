import { describe, it, expect } from 'vitest'
import type {
  Settings,
  OMEROInstance,
  ProgressInfo,
  ExecutionResult,
  ExecutionStatus,
} from '@/api/types'

describe('settings and execution type structures', () => {
  it('Settings has required fields', () => {
    const settings: Settings = {
      deployment_mode: 'desktop',
      output_data_folder: '/data/output',
    }
    expect(settings.deployment_mode).toBe('desktop')
    expect(settings.output_data_folder).toBe('/data/output')
  })

  it('Settings accepts all optional fields', () => {
    const settings: Settings = {
      deployment_mode: 'webapp',
      output_data_folder: '/out',
      external_editor: 'code {file_path}',
      napari_env_path: '/envs/napari',
      omero_instances: [],
      tool_store_path: '/tools',
      update_mode: 'manual',
      engine: 'wetlands',
      execution: 'parallel',
      execution_engine: 'sequential',
      keyboard_shortcuts: { run: 'Ctrl+R' },
      dev_mode: true,
      enable_unsafe_webapp_features: true,
    }
    expect(settings.engine).toBe('wetlands')
    expect(settings.execution).toBe('parallel')
  })

  it('OMEROInstance has required and optional fields', () => {
    const instance: OMEROInstance = {
      host: 'omero.example.com',
      username: 'admin',
    }
    expect(instance.host).toBe('omero.example.com')
    expect(instance.username).toBe('admin')
    expect(instance.name).toBeUndefined()
    expect(instance.port).toBeUndefined()
  })

  it('OMEROInstance with all fields', () => {
    const instance: OMEROInstance = {
      name: 'Production',
      host: 'omero.example.com',
      port: 4064,
      username: 'admin',
    }
    expect(instance.port).toBe(4064)
    expect(instance.name).toBe('Production')
  })

  it('ProgressInfo has required fields', () => {
    const progress: ProgressInfo = {
      node_id: 'node-1',
      row: 5,
      total_rows: 100,
      result_key: 'rk-node-1',
      record_id: 'rec-node-1',
    }
    expect(progress.node_id).toBe('node-1')
    expect(progress.row).toBe(5)
    expect(progress.total_rows).toBe(100)
    expect(progress.result_key).toBe('rk-node-1')
    expect(progress.record_id).toBe('rec-node-1')
  })

  it('ExecutionResult has required fields', () => {
    const result: ExecutionResult = {
      success: true,
      errors: [],
      node_statuses: {
        n1: {
          node_id: 'n1',
          status: 'executed',
          cached: false,
          result_key: 'rk-n1',
          record_id: 'rec-n1',
        },
      },
    }
    expect(result.success).toBe(true)
    expect(result.errors).toEqual([])
    expect(result.node_statuses.n1.status).toBe('executed')
    expect(result.node_statuses.n1.result_key).toBe('rk-n1')
    expect(result.node_statuses.n1.record_id).toBe('rec-n1')
  })

  it('ExecutionStatus has required fields', () => {
    const status: ExecutionStatus = {
      state: 'idle',
      last_result: null,
      progress: null,
    }
    expect(status.state).toBe('idle')
    expect(status.last_result).toBeNull()
    expect(status.progress).toBeNull()
  })

  it('ExecutionStatus with populated fields', () => {
    const status: ExecutionStatus = {
      state: 'running',
      last_result: {
        success: false,
        errors: [{ message: 'fail' }],
        node_statuses: {
          n1: { node_id: 'n1', status: 'failed', cached: false, error: 'boom' },
        },
      },
      progress: { node_id: 'n1', row: 3, total_rows: 10 },
    }
    expect(status.state).toBe('running')
    expect(status.last_result?.success).toBe(false)
    expect(status.progress?.row).toBe(3)
  })
})
