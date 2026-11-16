/** Workspace paths come from the backend's canonical workspace authority. */
export interface AutoSaveOwner {
  workspace_path: string
  identity_generation: number
}

export function recoveryOwnerKey(name: string, owner: AutoSaveOwner): string {
  return JSON.stringify([owner.workspace_path, name, owner.identity_generation])
}

export function recoveryEntryId(entry: { name: string; recovery_key?: string }): string {
  return entry.recovery_key ?? JSON.stringify(['legacy', entry.name])
}
