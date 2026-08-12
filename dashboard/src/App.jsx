import { useState, useEffect, useRef } from 'react'

function App() {
  // ── State ──
  const [config, setConfig] = useState({ url: '', username: '', password: '', tasks: [] })
  const [envUrl, setEnvUrl] = useState('')
  const [envUser, setEnvUser] = useState('')
  const [envPass, setEnvPass] = useState('')
  const [selectedTasks, setSelectedTasks] = useState(new Set())
  const [essEnabled, setEssEnabled] = useState(true)
  const [running, setRunning] = useState(false)
  const [logs, setLogs] = useState([])
  const [exitCode, setExitCode] = useState(null)
  const [elapsed, setElapsed] = useState(0)
  const logRef = useRef(null)
  const timerRef = useRef(null)
  const [pollTimeout, setPollTimeout] =useState('30:00')

  // ── Load config from Flask on mount ──
  useEffect(() => {
    fetch('/api/config')
      .then(r => r.json())
      .then(data => {
        setConfig(data)
        setEnvUrl(data.url || '')
        setEnvUser(data.username || '')
        setEnvPass(data.password || '')
        // Select all tasks by default
        const allNums = new Set(data.tasks.map(t => t.num))
        setSelectedTasks(allNums)
      })
      .catch(() => {})
  }, [])

  // ── Auto-scroll log ──
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [logs])

  // ── Timer ──
  useEffect(() => {
    if (running) {
      timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000)
    } else {
      clearInterval(timerRef.current)
    }
    return () => clearInterval(timerRef.current)
  }, [running])

  // ── Task selection helpers ──
  const toggleTask = (num) => {
    setSelectedTasks(prev => {
      const next = new Set(prev)
      next.has(num) ? next.delete(num) : next.add(num)
      return next
    })
  }

  const selectAll = () => {
    const allNums = new Set(config.tasks.map(t => t.num))
    setSelectedTasks(allNums)
    setEssEnabled(true)
  }

  const selectNone = () => {
    setSelectedTasks(new Set())
    setEssEnabled(false)
  }

  const selectUIOnly = () => {
    const uiNums = new Set(config.tasks.filter(t => t.category === 'ui').map(t => t.num))
    setSelectedTasks(uiNums)
    setEssEnabled(false)
  }

  // ── Log line classification ──
  const classifyLine = (text) => {
    if (text.includes('START =====')) return 'task-start'
    if (text.includes('DONE =====')) return 'task-done'
    if (text.includes('FAILED') || text.includes('ERROR') || text.includes('CRASHED')) return 'error'
    if (text.includes('WARNING') || text.includes('SKIPPED')) return 'warning'
    if (text.includes('SUCCEEDED') || text.includes('SUCCESS') || text.includes('successful') || text.includes('COMPLETE')) return 'success'
    if (text.includes('PHASE 2') || text.includes('POLLING') || text.includes('REST API')) return 'phase'
    return 'info'
  }

  // ── Build tasks string ──
  const getTasksArg = () => {
    const allTaskNums = new Set(config.tasks.map(t => t.num))
    const allSelected = selectedTasks.size === allTaskNums.size && 
      [...allTaskNums].every(n => selectedTasks.has(n)) && essEnabled
    if (allSelected) return 'all'
    
    const parts = [...selectedTasks].sort((a, b) => a - b).map(String)
    if (essEnabled) parts.push('ESS')
    return parts.join(',') || 'none'
  }

  // ── Start run ──
  const startRun = () => {
    if (!envUrl || !envUser || !envPass) {
      setLogs([{ text: 'Please fill in URL, Username, and Password.', cls: 'error' }])
      return
    }
    const toSeconds = (v) => {
      const s = String(v).trim()
      if (s.includes(':')) {
        const [m, sec] = s.split(':').map(n => parseInt(n, 10) || 0)
        return m * 60 + sec
      }
      return parseInt(s, 10) || 1800
    }

    const tasksArg = getTasksArg()
    if (tasksArg === 'none') {
      setLogs([{ text: 'No tasks selected. Check at least one task or ESS.', cls: 'error' }])
      return
    }

    setLogs([])
    setExitCode(null)
    setElapsed(0)
    setRunning(true)

    fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tasks: tasksArg,
        url: envUrl,
        username: envUser,
        password: envPass,
        poll_timeout: toSeconds(pollTimeout),
      })
    })
      .then(r => r.json())
      .then(data => {
        if (data.status === 'started') {
          // Connect SSE
          const es = new EventSource('/api/stream')
          es.onmessage = (e) => {
            const msg = JSON.parse(e.data)
            if (msg.type === 'log') {
              setLogs(prev => [...prev, { text: msg.text, cls: classifyLine(msg.text) }])
            } else if (msg.type === 'done') {
              es.close()
              setRunning(false)
              setExitCode(msg.code)
            }
            // ignore keepalive
          }
          es.onerror = () => {
            es.close()
            setRunning(false)
          }
        } else {
          setLogs([{ text: `Error: ${data.message}`, cls: 'error' }])
          setRunning(false)
        }
      })
      .catch(err => {
        setLogs([{ text: `Failed to connect: ${err}`, cls: 'error' }])
        setRunning(false)
      })
  }

  // ── Stop run ──
  const stopRun = () => {
    fetch('/api/stop', { method: 'POST' })
      .then(r => r.json())
      .then(() => {
        setRunning(false)
        setLogs(prev => [...prev, { text: 'Run stopped by user.', cls: 'warning' }])
      })
      .catch(() => {})
  }

  // ── Format elapsed time ──
  const formatTime = (s) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return m > 0 ? `${m}m ${sec}s` : `${sec}s`
  }

  // ── Count results from logs ──
  const countResults = () => {
    let passed = 0, failed = 0, skipped = 0
    logs.forEach(l => {
      if (l.cls === 'task-done') passed++
      if (l.text.includes('FAILED') && l.text.includes('=====')) failed++
      if (l.text.includes('SKIPPED (continued)')) skipped++
    })
    return { passed, failed, skipped }
  }

  const results = countResults()

  return (
    <div className="min-h-screen bg-[#0a0e17] text-[#e2e8f0] font-[Outfit,sans-serif]">
      {/* ── Header ── */}
      <header className="bg-gradient-to-r from-[#111827] to-[#1a2234] border-b border-[#2a3654] px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold tracking-tight">
          <span className="text-[#3b82f6]">P2T</span> Post-Refresh Automation
        </h1>
        <div className="flex items-center gap-4">
          {running && (
            <span className="font-mono text-sm text-[#94a3b8]">{formatTime(elapsed)}</span>
          )}
          <span className={`px-3 py-1.5 rounded-full text-xs font-mono font-medium
            ${running ? 'bg-[#3b82f6]/20 border border-[#3b82f6] text-[#3b82f6] animate-pulse' :
              exitCode === null ? 'bg-[#1a2234] border border-[#2a3654] text-[#94a3b8]' :
              exitCode === 0 ? 'bg-[#10b981]/20 border border-[#10b981] text-[#10b981]' :
              'bg-[#ef4444]/20 border border-[#ef4444] text-[#ef4444]'}`}>
            {running ? 'RUNNING' : exitCode === null ? 'IDLE' : exitCode === 0 ? 'COMPLETE' : 'FAILED'}
          </span>
        </div>
      </header>

      {/* ── Main Layout ── */}
      <div className="grid grid-cols-[380px_1fr] h-[calc(100vh-65px)]">
        
        {/* ── Sidebar ── */}
        <aside className="bg-[#111827] border-r border-[#2a3654] overflow-y-auto p-5">
          
          {/* Environment */}
          <p className="text-[0.7rem] font-semibold uppercase tracking-widest text-[#64748b] mb-3">Environment</p>
          <div className="flex flex-col gap-2.5 mb-5">
            <div>
              <label className="text-xs text-[#94a3b8] font-medium">Instance URL</label>
              <input type="text" value={envUrl} onChange={e => setEnvUrl(e.target.value)}
                className="w-full mt-1 bg-[#1a2234] border border-[#2a3654] rounded-md px-3 py-2 text-sm font-mono text-[#e2e8f0] outline-none focus:border-[#3b82f6] transition-colors"
                placeholder="https://...oraclecloud.com" />
            </div>
            <div>
              <label className="text-xs text-[#94a3b8] font-medium">Username</label>
              <input type="text" value={envUser} onChange={e => setEnvUser(e.target.value)}
                className="w-full mt-1 bg-[#1a2234] border border-[#2a3654] rounded-md px-3 py-2 text-sm font-mono text-[#e2e8f0] outline-none focus:border-[#3b82f6] transition-colors"
                placeholder="Username" />
            </div>
            <div>
              <label className="text-xs text-[#94a3b8] font-medium">Password</label>
              <input type="password" value={envPass} onChange={e => setEnvPass(e.target.value)}
                className="w-full mt-1 bg-[#1a2234] border border-[#2a3654] rounded-md px-3 py-2 text-sm font-mono text-[#e2e8f0] outline-none focus:border-[#3b82f6] transition-colors"
                placeholder="Password" />
            </div>
          </div>

          {/* Tasks */}
          <p className="text-[0.7rem] font-semibold uppercase tracking-widest text-[#64748b] mb-2">UI Tasks</p>
          <div className="flex gap-2 mb-3">
            <button onClick={selectAll} className="flex-1 py-1.5 rounded-md border border-[#2a3654] bg-[#1a2234] text-[#94a3b8] text-[0.72rem] hover:border-[#3b82f6] hover:text-[#3b82f6] transition-colors">
              Select All
            </button>
            <button onClick={selectNone} className="flex-1 py-1.5 rounded-md border border-[#2a3654] bg-[#1a2234] text-[#94a3b8] text-[0.72rem] hover:border-[#3b82f6] hover:text-[#3b82f6] transition-colors">
              None
            </button>
            <button onClick={selectUIOnly} className="flex-1 py-1.5 rounded-md border border-[#2a3654] bg-[#1a2234] text-[#94a3b8] text-[0.72rem] hover:border-[#3b82f6] hover:text-[#3b82f6] transition-colors">
              UI Only
            </button>
          </div>

          <div className="flex flex-col gap-0.5 mb-4">
            {config.tasks.map(task => (
              <label key={task.num}
                className="flex items-center gap-2.5 px-2.5 py-1.5 rounded-md cursor-pointer hover:bg-[#1f2b42] transition-colors text-[0.82rem]">
                <input type="checkbox" checked={selectedTasks.has(task.num)}
                  onChange={() => toggleTask(task.num)}
                  className="accent-[#3b82f6] w-[15px] h-[15px] cursor-pointer" />
                <span className="font-mono text-[0.7rem] text-[#64748b] min-w-[28px]">{task.num}</span>
                <span className={task.category === 'setup' ? 'text-[#f59e0b]' : ''}>{task.name}</span>
              </label>
            ))}
          </div>

          {/* ESS Toggle */}
          <p className="text-[0.7rem] font-semibold uppercase tracking-widest text-[#64748b] mb-2">ESS Jobs</p>
          <label className="flex items-center gap-2.5 px-3 py-2.5 bg-[#1a2234] border border-[#2a3654] rounded-md cursor-pointer text-sm">
            <input type="checkbox" checked={essEnabled} onChange={e => setEssEnabled(e.target.checked)}
              className="accent-[#3b82f6] w-[15px] h-[15px] cursor-pointer" />
            Run ESS Jobs (REST API + UI Retry)
          </label>

          <div className="mt-3">
            <label className="text-xs text-[#94a3b8] font-medium">ESS Poll Timeout (mm:ss)</label>
            <input type="text" value={pollTimeout} onChange={e => setPollTimeout(e.target.value)}
              className="w-full mt-1 bg-[#1a2234] border border-[#2a3654] rounded-md px-3 py-2 text-sm font-mono text-[#e2e8f0] outline-none focus:border-[#3b82f6] transition-colors"
              placeholder="30:00" />
          </div>

          {/* Run / Stop Button */}
          {!running ? (
            <button onClick={startRun}
              className="w-full mt-5 py-3 rounded-lg font-semibold text-white bg-gradient-to-r from-[#3b82f6] to-[#2563eb] shadow-[0_4px_15px_rgba(59,130,246,0.3)] hover:shadow-[0_6px_25px_rgba(59,130,246,0.4)] hover:-translate-y-0.5 transition-all tracking-wide">
              Run Automation
            </button>
          ) : (
            <button onClick={stopRun}
              className="w-full mt-5 py-3 rounded-lg font-semibold text-white bg-gradient-to-r from-[#ef4444] to-[#dc2626] shadow-[0_4px_15px_rgba(239,68,68,0.3)] transition-all tracking-wide">
              Stop Run
            </button>
          )}

          {/* Results Summary (after run) */}
          {exitCode !== null && (
            <div className="mt-4 p-3 rounded-lg border border-[#2a3654] bg-[#1a2234]">
              <p className="text-xs font-semibold uppercase tracking-widest text-[#64748b] mb-2">Results</p>
              <div className="flex gap-3">
                <div className="flex-1 text-center p-2 rounded-md bg-[#10b981]/10 border border-[#10b981]/30">
                  <div className="text-lg font-bold text-[#10b981]">{results.passed}</div>
                  <div className="text-[0.65rem] text-[#10b981]/70 uppercase">Passed</div>
                </div>
                <div className="flex-1 text-center p-2 rounded-md bg-[#ef4444]/10 border border-[#ef4444]/30">
                  <div className="text-lg font-bold text-[#ef4444]">{results.failed}</div>
                  <div className="text-[0.65rem] text-[#ef4444]/70 uppercase">Failed</div>
                </div>
                <div className="flex-1 text-center p-2 rounded-md bg-[#f59e0b]/10 border border-[#f59e0b]/30">
                  <div className="text-lg font-bold text-[#f59e0b]">{results.skipped}</div>
                  <div className="text-[0.65rem] text-[#f59e0b]/70 uppercase">Skipped</div>
                </div>
              </div>
              <div className="mt-2 text-center text-xs text-[#64748b]">
                Completed in {formatTime(elapsed)}
              </div>
            </div>
          )}
        </aside>

        {/* ── Log Panel ── */}
        <main className="flex flex-col bg-[#0a0e17]">
          <div className="px-5 py-3 bg-[#111827] border-b border-[#2a3654] flex justify-between items-center">
            <h3 className="text-sm font-medium text-[#94a3b8]">Live Output</h3>
            <button onClick={() => setLogs([])}
              className="px-3 py-1 rounded border border-[#2a3654] text-[0.7rem] text-[#64748b] hover:border-[#94a3b8] hover:text-[#94a3b8] transition-colors">
              Clear
            </button>
          </div>
          <div ref={logRef} className="flex-1 overflow-y-auto p-5 font-mono text-[0.75rem] leading-relaxed">
            {logs.length === 0 && !running && (
              <div className="text-[#64748b]">Ready. Select tasks and click "Run Automation" to begin.</div>
            )}
            {logs.map((line, i) => (
              <div key={i} className={`mb-0.5 ${
                line.cls === 'task-start' ? 'text-[#3b82f6] font-bold' :
                line.cls === 'task-done' ? 'text-[#10b981] font-bold' :
                line.cls === 'error' ? 'text-[#ef4444]' :
                line.cls === 'warning' ? 'text-[#f59e0b]' :
                line.cls === 'success' ? 'text-[#10b981]' :
                line.cls === 'phase' ? 'text-[#8b5cf6]' :
                'text-[#94a3b8]'
              }`}>
                {line.text}
              </div>
            ))}
            {running && (
              <div className="text-[#3b82f6] animate-pulse mt-1">▌</div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}

export default App