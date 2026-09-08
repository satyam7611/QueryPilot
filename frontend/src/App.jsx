import React, { useState, useRef, useEffect } from 'react';

const API_BASE = 'http://localhost:8000/api';

export default function App() {
  // Key configuration states (transient in-memory)
  const [apiKeyMode, setApiKeyMode] = useState('demo'); // 'demo' | 'byok'
  const [byokKey, setByokKey] = useState('');
  
  // Dataset context states
  const [activeDatasetId, setActiveDatasetId] = useState(null); // null means demo DB mode
  const [activeFilename, setActiveFilename] = useState('E-Commerce Demo Database');
  const [schemaDdl, setSchemaDdl] = useState('');
  const [schemaColumns, setSchemaColumns] = useState([]);
  
  // Loading & status states
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [queryInput, setQueryInput] = useState('');
  const [queryStatus, setQueryStatus] = useState('idle'); // 'idle' | 'running' | 'clarification' | 'completed' | 'failed'
  
  // Query response outputs
  const [activeThreadId, setActiveThreadId] = useState(null);
  const [generatedSql, setGeneratedSql] = useState('');
  const [finalAnswer, setFinalAnswer] = useState('');
  const [rawTableData, setRawTableData] = useState('');
  const [parsedTable, setParsedTable] = useState({ headers: [], rows: [] });
  const [errorMessage, setErrorMessage] = useState('');
  const [copiedSql, setCopiedSql] = useState(false);
  
  // Clarification states
  const [clarificationQuestion, setClarificationQuestion] = useState('');
  const [clarificationOptions, setClarificationOptions] = useState([]);
  
  // Reference for file input
  const fileInputRef = useRef(null);

  // Load the default demo schema DDL on mount
  useEffect(() => {
    if (!activeDatasetId) {
      setSchemaDdl(
        `-- Table: customers (Customer profiles)\n-- Table: products (Store items catalog)\n-- Table: orders (Order transaction headers)\n-- Table: order_items (Item-level purchase details)\n-- Table: payments (Payment validation logs)`
      );
      setSchemaColumns([
        { col: 'customers', type: 'customer_id, name, email, signup_date, country' },
        { col: 'products', type: 'product_id, name, category, price' },
        { col: 'orders', type: 'order_id, customer_id, order_date, total_amount, status' },
        { col: 'order_items', type: 'order_item_id, order_id, product_id, quantity, unit_price' },
        { col: 'payments', type: 'payment_id, order_id, payment_date, amount, payment_status' }
      ]);
    }
  }, [activeDatasetId]);

  // Helper to parse pipe-delimited table rows returned from psycopg tool
  const parsePipeTable = (rawString) => {
    if (!rawString || typeof rawString !== 'string') return { headers: [], rows: [] };
    
    // Check if it's a zero-rows notice
    if (rawString.includes("returned 0 rows") || rawString.includes("executed successfully")) {
      return { headers: [], rows: [[rawString]] };
    }
    
    const lines = rawString.split('\n').map(line => line.strip ? line.strip() : line.trim()).filter(line => line);
    if (lines.length === 0) return { headers: [], rows: [] };
    
    // Headers are the first line split by pipe
    const headers = lines[0].split('|').map(h => h.trim());
    
    // Skip index 1 since it's the dashed line (e.g. -----------)
    const rows = [];
    const startIndex = (lines.length > 1 && lines[1].includes('-')) ? 2 : 1;
    
    for (let i = startIndex; i < lines.length; i++) {
      if (lines[i].includes('results truncated')) {
        rows.push([lines[i]]); // Append truncation alert row
        continue;
      }
      const cols = lines[i].split('|').map(c => c.trim());
      rows.push(cols);
    }
    
    return { headers, rows };
  };

  // Triggers file selection
  const handleUploadClick = () => {
    fileInputRef.current.click();
  };

  // Upload file handler
  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    
    setIsUploading(true);
    setUploadError('');
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const response = await fetch(`${API_BASE}/datasets/upload`, {
        method: 'POST',
        body: formData,
        // Carry anonymous session cookie if available
        credentials: 'include'
      });
      
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Failed to upload dataset.');
      }
      
      const newDatasetId = data.dataset_id;
      setActiveDatasetId(newDatasetId);
      setActiveFilename(data.filename);
      
      // Fetch dynamic DDL
      const ddlResponse = await fetch(`${API_BASE}/datasets/${newDatasetId}/schema`, {
        credentials: 'include'
      });
      const ddlData = await ddlResponse.json();
      
      if (ddlResponse.ok) {
        setSchemaDdl(ddlData.ddl);
        // Parse simple columns list from DDL string for visual schema sidebar
        const lines = ddlData.ddl.split('\n');
        const parsedCols = [];
        lines.forEach(line => {
          if (line.includes('CREATE TABLE')) return;
          if (line.includes(');')) return;
          const match = line.match(/^\s*"?([a-zA-Z0-9_]+)"?\s+([A-Z0-9\(\),]+)/i);
          if (match) {
            parsedCols.push({ col: match[1], type: match[2].toLowerCase() });
          }
        });
        setSchemaColumns(parsedCols);
      }
      
    } catch (err) {
      console.error(err);
      setUploadError(err.message || 'Error processing file.');
    } finally {
      setIsUploading(false);
      // Reset input value to allow uploading same file
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Switch back to Default Demo Database
  const resetToDemoMode = () => {
    setActiveDatasetId(null);
    setActiveFilename('E-Commerce Demo Database');
    setSchemaDdl('');
  };

  // Submits a query
  const handleQuerySubmit = async (e) => {
    if (e) e.preventDefault();
    if (!queryInput.trim()) return;
    
    setQueryStatus('running');
    setErrorMessage('');
    setGeneratedSql('');
    setFinalAnswer('');
    setParsedTable({ headers: [], rows: [] });
    
    const payload = {
      question: queryInput,
      dataset_id: activeDatasetId,
      api_key: apiKeyMode === 'byok' ? byokKey : null
    };
    
    try {
      const response = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'An error occurred during query generation.');
      }
      
      handleApiResponse(data);
      
    } catch (err) {
      console.error(err);
      setQueryStatus('failed');
      setErrorMessage(err.message || 'Failed to submit query.');
    }
  };

  // Resumes clarification thread
  const handleClarificationSelection = async (choice) => {
    setQueryStatus('running');
    
    const payload = {
      thread_id: activeThreadId,
      choice: String(choice),
      api_key: apiKeyMode === 'byok' ? byokKey : null
    };
    
    try {
      const response = await fetch(`${API_BASE}/query/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Failed to resume clarification thread.');
      }
      
      handleApiResponse(data);
      
    } catch (err) {
      console.error(err);
      setQueryStatus('failed');
      setErrorMessage(err.message || 'Error resuming query.');
    }
  };

  // Helper handling backend API payload routing
  const handleApiResponse = (data) => {
    setActiveThreadId(data.thread_id);
    
    if (data.status === 'clarification_required') {
      setQueryStatus('clarification');
      setClarificationQuestion(data.question);
      setClarificationOptions(data.options || []);
    } else if (data.status === 'completed') {
      setQueryStatus('completed');
      setGeneratedSql(data.generated_sql || '');
      setFinalAnswer(data.final_answer || '');
      setRawTableData(data.query_result || '');
      setParsedTable(parsePipeTable(data.query_result));
      if (data.error) {
        setErrorMessage(data.error);
      }
    } else {
      setQueryStatus('failed');
      setErrorMessage(data.error || 'Agent execution failed.');
    }
  };

  return (
    <div>
      <div className="header-glow"></div>
      
      <div className="app-container">
        
        {/* App Title Header */}
        <header className="app-header">
          <div className="app-title-group">
            <span className="logo-badge">QP</span>
            <div>
              <h1>QueryPilot</h1>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Stateful Agentic Text-to-SQL Interface
              </p>
            </div>
          </div>
          
          {/* BYOK Configuration Control */}
          <div className="glass-card header-controls">
            <span className="header-controls-label">API Provider:</span>
            <div className="pill-group">
              <button 
                type="button"
                className={`pill-btn ${apiKeyMode === 'demo' ? 'active' : ''}`}
                onClick={() => setApiKeyMode('demo')}
              >
                QueryPilot Demo Key
              </button>
              <button 
                type="button"
                className={`pill-btn ${apiKeyMode === 'byok' ? 'active' : ''}`}
                onClick={() => setApiKeyMode('byok')}
              >
                Use My API Key
              </button>
            </div>
            
            {apiKeyMode === 'byok' && (
              <input 
                type="password" 
                placeholder="Enter Gemini / Groq API Key..."
                className="text-input byok-input"
                value={byokKey}
                onChange={(e) => setByokKey(e.target.value)}
              />
            )}
          </div>
        </header>

        {/* Dashboard Grid split into Controls & Output */}
        <main className="dashboard-grid">
          
          {/* Sidebar Panel: Data & Schemas */}
          <section className="sidebar-section">
            
            {/* Dataset Seeding card */}
            <div className="glass-card glow-card">
              <h3 style={{ marginBottom: '0.25rem' }}>Datasets</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '1rem', wordBreak: 'break-word' }}>
                Active: <span style={{ color: '#a78bfa', fontWeight: 600 }}>{activeFilename}</span>
              </p>
              
              <input 
                type="file" 
                ref={fileInputRef} 
                style={{ display: 'none' }} 
                accept=".csv, .xlsx"
                onChange={handleFileUpload} 
              />
              
              <div className="upload-dropzone" onClick={handleUploadClick}>
                <span className="upload-icon">📁</span>
                <span style={{ fontWeight: 500, fontSize: '0.9rem' }}>Upload CSV / XLSX</span>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                  Limits: 10MB per file
                </p>
              </div>
              
              {isUploading && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '1rem', color: '#a78bfa' }}>
                  <div className="spinner"></div>
                  <span style={{ fontSize: '0.85rem' }}>Ingesting dataset into database...</span>
                </div>
              )}
              
              {uploadError && (
                <div className="error-banner" style={{ marginTop: '0.75rem', padding: '0.6rem 0.85rem' }}>
                  <p>⚠️ {uploadError}</p>
                </div>
              )}
              
              {activeDatasetId && (
                <button 
                  className="btn btn-secondary" 
                  style={{ width: '100%', marginTop: '1rem', fontSize: '0.85rem', padding: '0.5rem' }}
                  onClick={resetToDemoMode}
                >
                  Reset to Demo Database
                </button>
              )}
            </div>
            
            {/* Active Schema display card */}
            <div className="glass-card" style={{ flexGrow: 1 }}>
              <h3>Schema Explorer</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Dynamic columns and structures detected
              </p>
              
              <div className="schema-list">
                {schemaColumns.length > 0 ? (
                  schemaColumns.map((item, index) => (
                    <div key={index} className="schema-item">
                      <span className="schema-item-name">
                        {item.col}
                      </span>
                      <span className="schema-type">
                        {item.type}
                      </span>
                    </div>
                  ))
                ) : (
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '1rem' }}>
                    No tables detected.
                  </p>
                )}
              </div>
              
              {schemaDdl && (
                <div style={{ marginTop: '1rem' }}>
                  <span className="input-label" style={{ fontSize: '0.75rem' }}>Raw Table Schema:</span>
                  <pre className="raw-schema-pre">
                    {schemaDdl}
                  </pre>
                </div>
              )}
            </div>
            
          </section>

          {/* Main Execution Output Panel */}
          <section className="main-section">
            
            {/* Input Form area */}
            <div className="glass-card glow-card">
              <h3>Ask Your Data</h3>
              <form onSubmit={handleQuerySubmit} style={{ marginTop: '1rem' }}>
                <textarea 
                  rows="2"
                  placeholder="e.g., How many total products do we have in the Electronics category?"
                  className="text-input"
                  style={{ resize: 'vertical', minHeight: '68px', marginBottom: '0.75rem' }}
                  value={queryInput}
                  onChange={(e) => setQueryInput(e.target.value)}
                  disabled={queryStatus === 'running'}
                />
                
                <div className="form-action-row">
                  <button 
                    type="submit" 
                    className="btn btn-primary"
                    disabled={queryStatus === 'running' || !queryInput.trim()}
                  >
                    {queryStatus === 'running' ? (
                      <>
                        <div className="spinner"></div>
                        Generating SQL & Synthesizing Answer...
                      </>
                    ) : (
                      <>
                        <span>⚡</span> Run Query
                      </>
                    )}
                  </button>
                </div>
              </form>

              {/* Sample Queries suggestions (shown before query / when idle) */}
              {queryStatus === 'idle' && (
                <div className="suggestions-container">
                  <div className="suggestions-title">
                    <span>💡 Suggested questions:</span>
                  </div>
                  <div className="suggestions-chips">
                    {[
                      "How many total products are in each category?",
                      "What is the total revenue from completed orders?",
                      "List the top 5 customers by total spending",
                      "How many orders were placed by customers in the USA?"
                    ].map((sample, idx) => (
                      <button
                        key={idx}
                        type="button"
                        className="suggestion-chip"
                        onClick={() => setQueryInput(sample)}
                      >
                        {sample}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
            
            {/* Error notifications area */}
            {errorMessage && (
              <div className="error-banner">
                <h4>Execution Notice</h4>
                <p>{errorMessage}</p>
              </div>
            )}

            {/* Clarification Interruption Prompt */}
            {queryStatus === 'clarification' && (
              <div className="glass-card clarify-card">
                <div className="card-header-row">
                  <h3 style={{ color: '#c4b5fd' }}>Clarification Required</h3>
                  <span className="meta-badge">Human-in-the-Loop</span>
                </div>
                <p style={{ marginTop: '0.25rem', fontSize: '0.95rem' }}>{clarificationQuestion}</p>
                
                <div className="option-button-list">
                  {clarificationOptions.map((opt, idx) => (
                    <button 
                      key={idx}
                      className="option-choice-btn"
                      onClick={() => handleClarificationSelection(idx + 1)}
                    >
                      <span style={{ color: '#a78bfa', fontWeight: 700 }}>[{idx + 1}]</span>
                      <span>{opt}</span>
                    </button>
                  ))}
                  
                  {/* Text entry option fallback */}
                  <div className="custom-clarify-row">
                    <input 
                      type="text" 
                      placeholder="Or describe custom clarification here..." 
                      className="text-input"
                      id="customClarifyInput"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          handleClarificationSelection(e.target.value);
                          e.target.value = '';
                        }
                      }}
                    />
                    <button 
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => {
                        const el = document.getElementById('customClarifyInput');
                        const val = el ? el.value : '';
                        if (val.trim()) {
                          handleClarificationSelection(val);
                          if (el) el.value = '';
                        }
                      }}
                    >
                      Submit
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Query completed outputs (SQL, rows table, synthesized explanation) */}
            {queryStatus === 'completed' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                
                {/* 1. Generated SQL code card */}
                {generatedSql && (
                  <div className="glass-card">
                    <div className="card-header-row">
                      <h3 style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>Generated SQL Query</h3>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span className="meta-badge">PostgreSQL</span>
                        <button 
                          type="button" 
                          className="btn btn-secondary btn-sm"
                          onClick={() => {
                            navigator.clipboard.writeText(generatedSql);
                            setCopiedSql(true);
                            setTimeout(() => setCopiedSql(false), 2000);
                          }}
                        >
                          {copiedSql ? '✓ Copied' : '📋 Copy SQL'}
                        </button>
                      </div>
                    </div>
                    <div className="code-block" style={{ marginTop: '0.5rem' }}>
                      <pre><code>{generatedSql}</code></pre>
                    </div>
                  </div>
                )}
                
                {/* 2. SQL execution table preview card */}
                <div className="glass-card">
                  <div className="card-header-row">
                    <h3 style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>SQL Execution Result</h3>
                    {parsedTable.rows.length > 0 && (
                      <span className="meta-badge meta-badge-success">
                        {parsedTable.rows.length} {parsedTable.rows.length === 1 ? 'row' : 'rows'}
                      </span>
                    )}
                  </div>
                  
                  {parsedTable.headers.length > 0 ? (
                    <>
                      <div className="table-wrapper">
                        <table className="results-table">
                          <thead>
                            <tr>
                              {parsedTable.headers.map((h, i) => (
                                <th key={i}>{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {parsedTable.rows.map((row, rIdx) => (
                              <tr key={rIdx}>
                                {row.map((col, cIdx) => (
                                  <td key={cIdx} colSpan={row.length === 1 ? parsedTable.headers.length : 1}>
                                    {col === null || col === 'None' ? (
                                      <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>NULL</span>
                                    ) : col}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <p className="table-scroll-hint">👈 Swipe horizontally to view more columns 👉</p>
                    </>
                  ) : (
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '0.75rem', fontStyle: 'italic' }}>
                      No rows returned from this query.
                    </p>
                  )}
                </div>

                {/* 3. Synthesized natural language explanation card */}
                {finalAnswer && (
                  <div className="glass-card summary-card">
                    <div className="card-header-row">
                      <h3>Summary Answer</h3>
                      <span className="meta-badge meta-badge-success">AI Synthesis</span>
                    </div>
                    <p>
                      {finalAnswer}
                    </p>
                  </div>
                )}

              </div>
            )}
            
          </section>

        </main>
      </div>
    </div>
  );
}
