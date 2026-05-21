<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { 
  ArrowLeft, FileText, UploadCloud, BookOpen, Brain, 
  Sparkles, Music, Play, Pause, Download, Trash2, 
  PlusCircle, Save, Loader, AlertTriangle, Search, CheckCircle
} from 'lucide-vue-next'

const route = useRoute()
const projectId = ref(Number(route.params.id))
const API_BASE = 'http://localhost:8000'

// Tabs
const activeTab = ref('documents') // 'documents' | 'wiki' | 'script' | 'audio'

// Loading & UI States
const loading = ref(true)
const errorMsg = ref('')
const project = ref<any>(null)

// Documents State
const documents = ref<any[]>([])
const docTitle = ref('')
const docContent = ref('')
const uploadingDoc = ref(false)
const selectedDoc = ref<any>(null)

// Facts State
const facts = ref<any[]>([])
const buildingKB = ref(false)
const kbLogs = ref<string[]>([])
const searchFactQuery = ref('')

// Scripts State
const scriptsList = ref<any[]>([])
const selectedScriptId = ref<number | null>(null)
const activeScript = ref<any>(null)
const scriptPrompt = ref('')
const scriptLoops = ref(3)
const generatingScript = ref(false)
const scriptLogs = ref<string[]>([])

// Editing Script state
const isEditing = ref(false)
const editedLines = ref<any[]>([])
const editedTitle = ref('')
const savingScript = ref(false)

// Audio State
const synthesizingAudio = ref(false)
const audioProgress = ref('')
const generatedAudio = ref<any>(null)
const audioUrl = ref('')
const audioRef = ref<HTMLAudioElement | null>(null)
const isPlaying = ref(false)

// SSE Stream Helper using Fetch for POST requests
const runStream = async (url: string, body: any, onEvent: (data: any) => void) => {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const reader = response.body?.getReader()
  const decoder = new TextDecoder('utf-8')
  if (!reader) return

  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''

    for (const part of parts) {
      if (part.trim().startsWith('data:')) {
        const jsonStr = part.replace('data:', '').trim()
        try {
          const data = JSON.parse(jsonStr)
          onEvent(data)
        } catch (e) {
          console.error('Failed to parse SSE chunk:', e)
        }
      }
    }
  }
}

// Actions & Fetches
const fetchProjectDetails = async () => {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await axios.get(`${API_BASE}/projects/${projectId.value}`)
    project.value = res.data
    await Promise.all([
      fetchDocuments(),
      fetchFacts(),
      fetchScripts()
    ])
  } catch (err: any) {
    console.error('Error fetching project detail:', err)
    errorMsg.value = 'Failed to load project details.'
  } finally {
    loading.value = false
  }
}

const fetchDocuments = async () => {
  const res = await axios.get(`${API_BASE}/projects/${projectId.value}/documents`)
  documents.value = res.data || []
}

const fetchFacts = async () => {
  const res = await axios.get(`${API_BASE}/projects/${projectId.value}/facts`)
  facts.value = res.data || []
}

const fetchScripts = async () => {
  const res = await axios.get(`${API_BASE}/projects/${projectId.value}/scripts`)
  scriptsList.value = res.data || []
  if (scriptsList.value.length > 0 && !selectedScriptId.value) {
    selectedScriptId.value = scriptsList.value[0].id
  }
}

const handleUploadDoc = async () => {
  if (!docTitle.value.trim() || !docContent.value.trim()) return
  uploadingDoc.value = true
  try {
    await axios.post(`${API_BASE}/projects/${projectId.value}/documents`, {
      title: docTitle.value.trim(),
      content: docContent.value.trim()
    })
    docTitle.value = ''
    docContent.value = ''
    await fetchDocuments()
  } catch (err) {
    console.error(err)
    alert('Failed to upload document')
  } finally {
    uploadingDoc.value = false
  }
}

const handleBuildKB = async () => {
  buildingKB.value = true
  kbLogs.value = []
  kbLogs.value.push('Starting Knowledge Base Compiler...')
  try {
    await runStream(`${API_BASE}/projects/${projectId.value}/build-kb`, {}, (data) => {
      if (data.status) {
        kbLogs.value.push(data.status)
      }
      if (data.done) {
        kbLogs.value.push('Success! All facts extracted successfully.')
      }
    })
    await fetchFacts()
  } catch (err: any) {
    kbLogs.value.push(`[ERROR] Compile failed: ${err.message}`)
  } finally {
    buildingKB.value = false
  }
}

const handleGenerateScript = async () => {
  if (!scriptPrompt.value.trim()) return
  generatingScript.value = true
  scriptLogs.value = []
  scriptLogs.value.push('Initializing Google ADK orchestrator...')
  try {
    await runStream(
      `${API_BASE}/projects/${projectId.value}/generate-script`, 
      { prompt: scriptPrompt.value.trim(), max_loops: scriptLoops.value }, 
      (data) => {
        if (data.status) {
          scriptLogs.value.push(data.status)
        }
        if (data.done && data.script_id) {
          scriptLogs.value.push(`Script generated and saved! Script ID: ${data.script_id}`)
          selectedScriptId.value = data.script_id
          fetchScripts()
          activeTab.value = 'script'
        }
      }
    )
  } catch (err: any) {
    scriptLogs.value.push(`[ERROR] Script generation failed: ${err.message}`)
  } finally {
    generatingScript.value = false
  }
}

const handleReadScript = async (scriptId: number) => {
  try {
    const res = await axios.get(`${API_BASE}/projects/scripts/${scriptId}`)
    const fullScript = res.data
    activeScript.value = fullScript
    
    // Parse lines and personas
    const content = fullScript.content
    if (content && content.script) {
      editedLines.value = JSON.parse(JSON.stringify(content.script.lines || []))
      editedTitle.value = content.script.title || fullScript.title
    } else {
      editedLines.value = JSON.parse(JSON.stringify(content?.lines || []))
      editedTitle.value = fullScript.title
    }
    isEditing.value = false
    
    // Check if there is already an audio file for this script
    if (fullScript.audios && fullScript.audios.length > 0) {
      generatedAudio.value = fullScript.audios[0]
      audioUrl.value = `${API_BASE}/projects/audio/${generatedAudio.value.id}`
    } else {
      generatedAudio.value = null
      audioUrl.value = ''
    }
  } catch (err) {
    console.error('Error reading script:', err)
  }
}

const handleSaveScriptEdits = async () => {
  if (!selectedScriptId.value || !activeScript.value) return
  savingScript.value = true
  try {
    // Reconstruct content
    const updatedContent = {
      script: {
        title: editedTitle.value,
        lines: editedLines.value
      },
      personas: activeScript.value.content?.personas || { personas: [] }
    }
    
    await axios.put(`${API_BASE}/projects/scripts/${selectedScriptId.value}`, updatedContent)
    activeScript.value.content = updatedContent
    activeScript.value.title = editedTitle.value
    isEditing.value = false
    alert('Script updated successfully!')
  } catch (err) {
    console.error('Error saving script:', err)
    alert('Failed to save script edits.')
  } finally {
    savingScript.value = false
  }
}

const handleGenerateAudio = async () => {
  if (!selectedScriptId.value) return
  synthesizingAudio.value = true
  audioProgress.value = 'Preparing audio compilers...'
  try {
    const res = await axios.post(`${API_BASE}/projects/scripts/${selectedScriptId.value}/generate-audio`)
    generatedAudio.value = res.data
    audioUrl.value = `${API_BASE}${res.data.download_url}`
    audioProgress.value = 'Audio synthesis complete!'
    await fetchScripts() // refresh script list to link audio
    if (selectedScriptId.value) {
      await handleReadScript(selectedScriptId.value)
    }
  } catch (err: any) {
    console.error(err)
    audioProgress.value = `[ERROR] Synthesis failed: ${err.response?.data?.detail || err.message}`
  } finally {
    synthesizingAudio.value = false
  }
}

// Audio Player controls
const togglePlay = () => {
  if (!audioRef.value) return
  if (isPlaying.value) {
    audioRef.value.pause()
  } else {
    audioRef.value.play()
  }
  isPlaying.value = !isPlaying.value
}

// Persona management
const personasList = computed(() => {
  if (!activeScript.value?.content) return []
  return activeScript.value.content.personas?.personas || []
})

// Edit Line helpers
const deleteLine = (index: number) => {
  editedLines.value.splice(index, 1)
}

const addLine = (index: number) => {
  const speaker = personasList.value[0]?.name || 'Host'
  editedLines.value.splice(index + 1, 0, { speaker, text: '' })
}

// Fact filter
const filteredFacts = computed(() => {
  if (!searchFactQuery.value.trim()) return facts.value
  const q = searchFactQuery.value.toLowerCase()
  return facts.value.filter(f => 
    f.point.toLowerCase().includes(q) || 
    f.context.toLowerCase().includes(q)
  )
})

watch(selectedScriptId, (newId) => {
  if (newId) {
    handleReadScript(newId)
  } else {
    activeScript.value = null
    editedLines.value = []
  }
}, { immediate: true })

onMounted(() => {
  fetchProjectDetails()
})
</script>

<template>
  <div>
    <!-- Back Navigation -->
    <div class="mb-4">
      <router-link to="/" class="flex items-center gap-1.5 text-sm font-bold text-govuk-blue hover:underline">
        <ArrowLeft class="h-4 w-4" />
        Back to Dashboard
      </router-link>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex flex-col items-center justify-center py-20">
      <Loader class="h-12 w-12 text-govuk-blue animate-spin mb-4" />
      <p class="govuk-body text-govuk-grey-2">Retrieving project archives and script data...</p>
    </div>

    <!-- Error state -->
    <div v-else-if="errorMsg" class="bg-govuk-red/10 border-l-4 border-govuk-red p-6 mb-6">
      <h3 class="govuk-heading-m text-govuk-red flex items-center gap-2">
        <AlertTriangle class="h-6 w-6" />
        Archive Access Error
      </h3>
      <p class="govuk-body text-govuk-black">{{ errorMsg }}</p>
      <button @click="fetchProjectDetails" class="govuk-button mt-4">
        Retry Retrieval
      </button>
    </div>

    <!-- Project Room -->
    <div v-else-if="project">
      <div class="border-b-4 border-govuk-blue pb-4 mb-8">
        <div class="flex justify-between items-start gap-4">
          <div>
            <span class="bg-govuk-blue text-white px-2 py-0.5 text-xs font-bold tracking-wider rounded">
              DIRECTORY: #00{{ project.id }}
            </span>
            <h1 class="govuk-heading-l mt-2 mb-2">{{ project.name }}</h1>
            <p class="govuk-body text-govuk-grey-1 mb-0 text-base max-w-4xl">
              {{ project.description || 'No briefing description available.' }}
            </p>
          </div>
          <div class="text-right text-xs text-govuk-grey-2">
            <span>Created: {{ new Date(project.created_at).toLocaleDateString() }}</span>
          </div>
        </div>
      </div>

      <!-- Custom Tabs Navigation -->
      <div class="flex border-b-2 border-govuk-grey-3 mb-6 bg-govuk-grey-4 p-1 pb-0 gap-1 overflow-x-auto">
        <button 
          @click="activeTab = 'documents'"
          :class="['px-5 py-3 font-bold text-sm border-t-4 transition-all flex items-center gap-2', 
            activeTab === 'documents' 
              ? 'bg-govuk-white border-govuk-blue text-govuk-black shadow-sm' 
              : 'border-transparent text-govuk-grey-2 hover:bg-govuk-grey-3 hover:text-govuk-black']"
        >
          <FileText class="h-4.5 w-4.5" />
          <span>Source Documents ({{ documents.length }})</span>
        </button>

        <button 
          @click="activeTab = 'wiki'"
          :class="['px-5 py-3 font-bold text-sm border-t-4 transition-all flex items-center gap-2', 
            activeTab === 'wiki' 
              ? 'bg-govuk-white border-govuk-blue text-govuk-black shadow-sm' 
              : 'border-transparent text-govuk-grey-2 hover:bg-govuk-grey-3 hover:text-govuk-black']"
        >
          <Brain class="h-4.5 w-4.5" />
          <span>Fact Extractor & Wiki ({{ facts.length }})</span>
        </button>

        <button 
          @click="activeTab = 'script'"
          :class="['px-5 py-3 font-bold text-sm border-t-4 transition-all flex items-center gap-2', 
            activeTab === 'script' 
              ? 'bg-govuk-white border-govuk-blue text-govuk-black shadow-sm' 
              : 'border-transparent text-govuk-grey-2 hover:bg-govuk-grey-3 hover:text-govuk-black']"
        >
          <Sparkles class="h-4.5 w-4.5" />
          <span>Podcast Script Workspace ({{ scriptsList.length }})</span>
        </button>

        <button 
          @click="activeTab = 'audio'"
          :class="['px-5 py-3 font-bold text-sm border-t-4 transition-all flex items-center gap-2', 
            activeTab === 'audio' 
              ? 'bg-govuk-white border-govuk-blue text-govuk-black shadow-sm' 
              : 'border-transparent text-govuk-grey-2 hover:bg-govuk-grey-3 hover:text-govuk-black']"
        >
          <Music class="h-4.5 w-4.5" />
          <span>Audio Production</span>
        </button>
      </div>

      <!-- Tab Content Area -->
      <div class="bg-govuk-white min-h-[400px]">
        
        <!-- Tab 1: Source Documents -->
        <div v-if="activeTab === 'documents'" class="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <!-- Upload form -->
          <div class="lg:col-span-1 border-4 border-govuk-grey-3 p-6 bg-govuk-grey-4">
            <h3 class="govuk-heading-s flex items-center gap-2 mb-4">
              <UploadCloud class="h-5 w-5 text-govuk-blue" />
              Upload Source Document
            </h3>
            <form @submit.prevent="handleUploadDoc" class="space-y-4">
              <div>
                <label for="doc-title" class="block text-sm font-bold mb-1.5">Document Title</label>
                <input 
                  type="text" 
                  id="doc-title" 
                  v-model="docTitle" 
                  required 
                  placeholder="e.g. Chapter 1 Summary" 
                  class="govuk-input text-sm"
                />
              </div>
              <div>
                <label for="doc-content" class="block text-sm font-bold mb-1.5">Full Text Content</label>
                <textarea 
                  id="doc-content" 
                  v-model="docContent" 
                  rows="10" 
                  required 
                  placeholder="Paste raw research document or reference articles here..." 
                  class="govuk-input text-sm font-sans"
                ></textarea>
              </div>
              <button 
                type="submit" 
                :disabled="uploadingDoc || !docTitle.trim() || !docContent.trim()" 
                class="govuk-button w-full flex items-center justify-center gap-2"
              >
                <Loader v-if="uploadingDoc" class="h-4 w-4 animate-spin" />
                <span>Upload Document</span>
              </button>
            </form>
          </div>

          <!-- Document listing -->
          <div class="lg:col-span-2 space-y-4">
            <h3 class="govuk-heading-m">Integrated Source Materials</h3>
            <p v-if="documents.length === 0" class="govuk-body text-govuk-grey-2 border-2 border-dashed p-8 text-center">
              No files uploaded. Use the upload panel on the left to add primary source transcripts and research documents.
            </p>
            <div v-else class="space-y-3">
              <div 
                v-for="doc in documents" 
                :key="doc.id" 
                class="border-2 border-govuk-grey-3 p-4 hover:border-govuk-blue transition-all cursor-pointer bg-govuk-white flex justify-between items-center"
                @click="selectedDoc = doc"
              >
                <div class="flex items-center gap-3">
                  <FileText class="h-6 w-6 text-govuk-grey-2" />
                  <div>
                    <h4 class="font-bold text-govuk-black hover:text-govuk-blue">{{ doc.title }}</h4>
                    <p class="text-xs text-govuk-grey-2 mt-1">
                      Uploaded: {{ new Date(doc.created_at).toLocaleDateString() }} | Size: {{ doc.content?.length || 0 }} chars
                    </p>
                  </div>
                </div>
                <button class="govuk-button-secondary py-1 px-3 text-xs font-bold">
                  View File
                </button>
              </div>
            </div>

            <!-- Selected Document View Drawer -->
            <div v-if="selectedDoc" class="govuk-panel mt-6" id="selected-doc-drawer">
              <div class="flex justify-between items-start border-b border-govuk-grey-3 pb-2 mb-4">
                <h4 class="govuk-heading-s m-0 text-govuk-blue flex items-center gap-2">
                  <BookOpen class="h-5 w-5" />
                  {{ selectedDoc.title }}
                </h4>
                <button @click="selectedDoc = null" class="text-xs font-bold underline hover:text-govuk-red">
                  Close Preview
                </button>
              </div>
              <div class="bg-govuk-grey-4 p-4 max-h-[300px] overflow-y-auto rounded text-sm leading-relaxed whitespace-pre-wrap font-sans">
                {{ selectedDoc.content }}
              </div>
            </div>
          </div>
        </div>

        <!-- Tab 2: Fact Extraction & Wiki -->
        <div v-if="activeTab === 'wiki'" class="space-y-6">
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- Fact Extraction triggering panel -->
            <div class="lg:col-span-1 border-4 border-govuk-grey-3 p-6 bg-govuk-grey-4">
              <h3 class="govuk-heading-s flex items-center gap-2 mb-4">
                <Brain class="h-5 w-5 text-govuk-blue" />
                Knowledge Base Compiler
              </h3>
              <p class="text-sm text-govuk-grey-1 mb-4 leading-relaxed">
                Analyze all uploaded source documents using Gemini. This triggers the **Fact Extractor Agent** to scrape core truths, assertions, and verification quotes, storing them in an structured local Wiki.
              </p>
              
              <div class="bg-govuk-white border-2 border-govuk-blue p-4 mb-4 text-center">
                <span class="block text-2xl font-bold text-govuk-blue">{{ facts.length }}</span>
                <span class="text-xs uppercase tracking-wider text-govuk-grey-2">Facts Currently Extracted</span>
              </div>

              <button 
                @click="handleBuildKB" 
                :disabled="buildingKB || documents.length === 0" 
                class="govuk-button w-full flex items-center justify-center gap-2"
              >
                <Loader v-if="buildingKB" class="h-5 w-5 animate-spin" />
                <span>Build Knowledge Base</span>
              </button>
              <span v-if="documents.length === 0" class="block text-[11px] text-govuk-red mt-2 text-center font-bold">
                ⚠️ Upload at least one document first.
              </span>
            </div>

            <!-- Logs / Output Terminal -->
            <div class="lg:col-span-2 flex flex-col h-full min-h-[250px]">
              <h3 class="govuk-heading-s flex items-center gap-2">
                Compiler Status Console
              </h3>
              <div class="bg-govuk-black text-govuk-green p-4 font-mono text-xs rounded-md shadow-inner flex-grow max-h-[300px] overflow-y-auto leading-relaxed border-2 border-govuk-grey-3">
                <div v-if="kbLogs.length === 0" class="text-govuk-grey-2 italic">
                  Terminal idle. Ready to analyze archive material.
                </div>
                <div v-else v-for="(log, idx) in kbLogs" :key="idx" class="mb-1">
                  &gt; {{ log }}
                </div>
              </div>
            </div>
          </div>

          <!-- Fact graph explorer / Wiki -->
          <div class="border-t-4 border-govuk-grey-3 pt-6">
            <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-4">
              <h3 class="govuk-heading-m m-0">Project Knowledge Base Wiki</h3>
              <div class="relative w-full sm:w-72">
                <input 
                  type="text" 
                  v-model="searchFactQuery" 
                  placeholder="Search extracted facts..." 
                  class="govuk-input text-sm pl-9 py-1.5"
                />
                <Search class="absolute left-3 top-2.5 h-4.5 w-4.5 text-govuk-grey-2" />
              </div>
            </div>

            <div v-if="filteredFacts.length === 0" class="border-2 border-dashed p-8 text-center text-govuk-grey-2">
              No matching facts found. Compile the knowledge base or refine your search.
            </div>
            
            <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div 
                v-for="fact in filteredFacts" 
                :key="fact.id" 
                class="border-l-4 border-govuk-blue p-4 bg-govuk-grey-4/40 flex flex-col justify-between"
              >
                <div>
                  <p class="govuk-body text-sm font-bold text-govuk-black mb-2">
                    {{ fact.point }}
                  </p>
                  <blockquote class="border-l-2 border-govuk-grey-3 pl-3 italic text-xs text-govuk-grey-2 leading-relaxed bg-govuk-white p-2 mb-2 font-sans rounded">
                    "{{ fact.context }}"
                  </blockquote>
                </div>
                <div class="text-[10px] text-govuk-grey-2 flex justify-between items-center pt-2 mt-2 border-t border-govuk-grey-4">
                  <span>REF: Fact #{{ fact.id }}</span>
                  <span>Document #{{ fact.document_id }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Tab 3: Podcast Script Workspace -->
        <div v-if="activeTab === 'script'" class="space-y-6">
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- Form Parameters -->
            <div class="lg:col-span-1 border-4 border-govuk-grey-3 p-6 bg-govuk-grey-4">
              <h3 class="govuk-heading-s flex items-center gap-2 mb-4">
                <Sparkles class="h-5 w-5 text-govuk-blue" />
                Collaborative Script Writer
              </h3>
              
              <div class="space-y-4">
                <div>
                  <label class="block text-sm font-bold mb-1">Guiding Prompt / Focus</label>
                  <span class="block text-xs text-govuk-grey-2 mb-2">Direct the agents' scriptwriter style or main topics.</span>
                  <textarea 
                    v-model="scriptPrompt" 
                    rows="4" 
                    placeholder="e.g. Focus on summarizing the key conflicts, making it sound like an objective investigation. Ensure the tone is serious but highly engaging." 
                    class="govuk-input text-sm"
                  ></textarea>
                </div>

                <div>
                  <label class="block text-sm font-bold mb-1">Writer-Critic Cycles: {{ scriptLoops }}</label>
                  <span class="block text-xs text-govuk-grey-2 mb-2">How many passes of review before finishing (1-5).</span>
                  <input 
                    type="range" 
                    v-model.number="scriptLoops" 
                    min="1" 
                    max="5" 
                    class="w-full h-2 bg-govuk-grey-3 rounded-lg appearance-none cursor-pointer accent-govuk-blue"
                  />
                  <div class="flex justify-between text-xs text-govuk-grey-2 mt-1">
                    <span>1 (Fast)</span>
                    <span>3 (Balanced)</span>
                    <span>5 (Refined)</span>
                  </div>
                </div>

                <button 
                  @click="handleGenerateScript" 
                  :disabled="generatingScript || facts.length === 0 || !scriptPrompt.trim()" 
                  class="govuk-button w-full flex items-center justify-center gap-2"
                >
                  <Loader v-if="generatingScript" class="h-5 w-5 animate-spin" />
                  <span>Generate Script Dialogue</span>
                </button>
                
                <span v-if="facts.length === 0" class="block text-[11px] text-govuk-red mt-2 text-center font-bold">
                  ⚠️ Compile Knowledge Base first to feed data.
                </span>
              </div>
            </div>

            <!-- Agent Console -->
            <div class="lg:col-span-2 flex flex-col h-full min-h-[250px]">
              <h3 class="govuk-heading-s flex items-center gap-2">
                Agent Collaboration Feed
              </h3>
              <div class="bg-govuk-black text-govuk-green p-4 font-mono text-xs rounded-md shadow-inner flex-grow max-h-[300px] overflow-y-auto leading-relaxed border-2 border-govuk-grey-3">
                <div v-if="scriptLogs.length === 0" class="text-govuk-grey-2 italic">
                  Feed idle. Design a guiding prompt and generate script to stream real-time writer-critic collaboration.
                </div>
                <div v-else v-for="(log, idx) in scriptLogs" :key="idx" class="mb-1">
                  &gt; {{ log }}
                </div>
              </div>
            </div>
          </div>

          <!-- Script Workspace Listing & Active Script View -->
          <div class="border-t-4 border-govuk-grey-3 pt-6">
            <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-4 border-b border-govuk-grey-3 pb-3">
              <h3 class="govuk-heading-m m-0">Podcast Scripts</h3>
              
              <!-- Script Selector Dropdown -->
              <div class="flex items-center gap-2 w-full sm:w-auto" v-if="scriptsList.length > 0">
                <span class="text-sm font-bold whitespace-nowrap">Active File:</span>
                <select v-model="selectedScriptId" class="govuk-input text-xs py-1.5 pr-8">
                  <option v-for="s in scriptsList" :key="s.id" :value="s.id">
                    {{ s.title }}
                  </option>
                </select>
              </div>
            </div>

            <div v-if="scriptsList.length === 0" class="border-2 border-dashed p-8 text-center text-govuk-grey-2">
              No podcast scripts generated yet. Run the script writer tool above to draft your first podcast series.
            </div>

            <!-- Active Script Editing Workspace -->
            <div v-else-if="activeScript" class="space-y-6">
              
              <!-- Script header & editor actions -->
              <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center bg-govuk-grey-4 p-4 border-2 border-govuk-grey-3 rounded gap-4 shadow-sm">
                <div>
                  <div class="flex items-center gap-2">
                    <h3 class="govuk-heading-m m-0" v-if="!isEditing">{{ activeScript.title }}</h3>
                    <input 
                      v-else 
                      type="text" 
                      v-model="editedTitle" 
                      class="govuk-input text-base py-1 font-bold"
                    />
                    <span class="bg-govuk-green text-white text-[10px] px-1.5 py-0.5 font-bold uppercase rounded flex items-center gap-1">
                      <CheckCircle class="h-3 w-3" /> Persistent DB File
                    </span>
                  </div>
                  <p class="text-xs text-govuk-grey-2 mt-1">
                    Guidance prompt: "{{ activeScript.prompt }}"
                  </p>
                </div>

                <div class="flex items-center gap-3 w-full sm:w-auto">
                  <button 
                    v-if="!isEditing" 
                    @click="isEditing = true" 
                    class="govuk-button-secondary py-1.5 px-4 text-sm"
                  >
                    Edit Script Dialogue
                  </button>
                  <div v-else class="flex gap-2 w-full sm:w-auto">
                    <button 
                      @click="handleSaveScriptEdits" 
                      :disabled="savingScript" 
                      class="govuk-button py-1.5 px-4 text-sm flex items-center gap-1.5"
                    >
                      <Loader v-if="savingScript" class="h-4 w-4 animate-spin" />
                      <Save class="h-4 w-4" v-else />
                      <span>Save Changes</span>
                    </button>
                    <button 
                      @click="isEditing = false; handleReadScript(selectedScriptId!)" 
                      class="govuk-button-secondary py-1.5 px-4 text-sm"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>

              <!-- Persona Cards Summary -->
              <div v-if="personasList.length > 0" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div 
                  v-for="(persona, idx) in personasList" 
                  :key="idx" 
                  class="border-4 border-govuk-grey-3 p-4 bg-govuk-white"
                >
                  <div class="flex items-center gap-2 mb-2">
                    <span :class="['h-3 w-3 rounded-full', idx === 0 ? 'bg-govuk-blue' : 'bg-govuk-red']"></span>
                    <h4 class="font-bold text-govuk-black">{{ persona.name }}</h4>
                    <span class="text-xs text-govuk-grey-2">({{ persona.role }})</span>
                  </div>
                  <p class="text-xs text-govuk-grey-1 leading-relaxed m-0 font-sans">
                    {{ persona.description }}
                  </p>
                </div>
              </div>

              <!-- Interactive Dialogue Transcript Editor -->
              <div class="border-4 border-govuk-black p-6 bg-govuk-white space-y-4 max-h-[600px] overflow-y-auto shadow-inner rounded">
                <div v-if="editedLines.length === 0" class="text-center text-govuk-grey-2 py-8 italic">
                  Dialogue sheet empty.
                </div>
                
                <div 
                  v-for="(line, idx) in editedLines" 
                  :key="idx" 
                  :class="['flex flex-col gap-1 p-3 border rounded transition-all', 
                    line.speaker === (personasList[0]?.name || 'Host')
                      ? 'border-govuk-blue/30 bg-govuk-blue/5 mr-12' 
                      : 'border-govuk-red/30 bg-govuk-red/5 ml-12']"
                >
                  <!-- Line Header / Speaker selector -->
                  <div class="flex justify-between items-center text-xs font-bold border-b border-govuk-grey-3/30 pb-1 mb-2">
                    <div class="flex items-center gap-2">
                      <span :class="['h-2 w-2 rounded-full', line.speaker === (personasList[0]?.name || 'Host') ? 'bg-govuk-blue' : 'bg-govuk-red']"></span>
                      
                      <!-- Speaker view / dropdown -->
                      <span v-if="!isEditing" class="text-govuk-black">{{ line.speaker }}</span>
                      <select 
                        v-else 
                        v-model="line.speaker" 
                        class="border-2 border-govuk-black bg-white px-1 text-[11px]"
                      >
                        <option v-for="p in personasList" :key="p.name" :value="p.name">{{ p.name }}</option>
                        <option v-if="personasList.length === 0" value="Host">Host</option>
                        <option v-if="personasList.length === 0" value="Guest">Guest</option>
                      </select>
                    </div>

                    <!-- Row manipulation buttons during edit -->
                    <div v-if="isEditing" class="flex gap-2">
                      <button @click="addLine(idx)" class="text-govuk-green hover:underline flex items-center gap-0.5">
                        <PlusCircle class="h-3.5 w-3.5" /> Insert Below
                      </button>
                      <button @click="deleteLine(idx)" class="text-govuk-red hover:underline flex items-center gap-0.5">
                        <Trash2 class="h-3.5 w-3.5" /> Delete
                      </button>
                    </div>
                  </div>

                  <!-- Dialogue Content -->
                  <p v-if="!isEditing" class="m-0 text-sm leading-relaxed text-govuk-black font-sans select-all whitespace-pre-wrap">
                    {{ line.text }}
                  </p>
                  <textarea 
                    v-else 
                    v-model="line.text" 
                    rows="3" 
                    class="govuk-input text-xs font-sans bg-white p-2"
                  ></textarea>
                </div>
              </div>

              <!-- Footer Edit Indicator -->
              <div v-if="isEditing" class="flex justify-end gap-3">
                <button 
                  @click="handleSaveScriptEdits" 
                  :disabled="savingScript" 
                  class="govuk-button flex items-center gap-1.5"
                >
                  <Loader v-if="savingScript" class="h-4 w-4 animate-spin" />
                  <Save class="h-4 w-4" v-else />
                  <span>Save Changes</span>
                </button>
                <button 
                  @click="isEditing = false; handleReadScript(selectedScriptId!)" 
                  class="govuk-button-secondary"
                >
                  Cancel
                </button>
              </div>

            </div>
          </div>
        </div>

        <!-- Tab 4: Audio Production -->
        <div v-if="activeTab === 'audio'" class="space-y-6">
          <h3 class="govuk-heading-m">British Voice Synthesis & Compilation</h3>
          
          <div v-if="scriptsList.length === 0" class="border-2 border-dashed p-8 text-center text-govuk-grey-2">
            No podcast scripts available. Create a script in the Workspace tab first before compiling speech.
          </div>

          <div v-else class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- Control Synthesis Panel -->
            <div class="lg:col-span-1 border-4 border-govuk-grey-3 p-6 bg-govuk-grey-4">
              <label class="block text-sm font-bold mb-2">Select Target Script:</label>
              <select v-model="selectedScriptId" class="govuk-input text-sm mb-4">
                <option v-for="s in scriptsList" :key="s.id" :value="s.id">
                  {{ s.title }}
                </option>
              </select>

              <p class="text-xs text-govuk-grey-1 mb-4 leading-relaxed font-sans">
                Compiles the selected dialogue transcript using **Kokoro-82M** high-fidelity models for British English (using `bf_alice` as female host, and `bm_george` as male guest). 
                Segments are concatenated directly on the server with 0.5s natural speaking silences.
              </p>

              <button 
                @click="handleGenerateAudio" 
                :disabled="synthesizingAudio || !selectedScriptId" 
                class="govuk-button w-full flex items-center justify-center gap-2"
              >
                <Loader v-if="synthesizingAudio" class="h-5 w-5 animate-spin" />
                <Music class="h-5 w-5" v-else />
                <span>Synthesize British Audio</span>
              </button>
            </div>

            <!-- Progress Details / Audio Output Console -->
            <div class="lg:col-span-2 space-y-4">
              <h4 class="govuk-heading-s">Synthesis Progress Log</h4>
              <div class="bg-govuk-black text-govuk-green p-4 font-mono text-xs rounded-md shadow-inner min-h-[120px] max-h-[200px] overflow-y-auto leading-relaxed border-2 border-govuk-grey-3">
                <div v-if="audioProgress" class="mb-1">&gt; {{ audioProgress }}</div>
                <div v-if="synthesizingAudio" class="flex items-center gap-2 mt-2">
                  <span class="h-2 w-2 rounded-full bg-govuk-green animate-ping"></span>
                  <span class="text-xs italic text-govuk-grey-3">Synthesizing audio nodes on the server, please wait...</span>
                </div>
                <div v-else-if="!audioProgress" class="text-govuk-grey-2 italic">
                  Waiting to synthesize speech blocks.
                </div>
              </div>

              <!-- High Premium dark-mode Audio Player Card -->
              <div 
                v-if="audioUrl" 
                class="bg-govuk-black border-4 border-govuk-blue text-white p-6 shadow-xl flex flex-col md:flex-row items-center justify-between gap-6 transition-all duration-300 rounded"
              >
                <div class="flex items-center gap-4">
                  <div class="bg-govuk-blue p-3.5 text-white rounded-full">
                    <Music class="h-7 w-7" />
                  </div>
                  <div>
                    <h4 class="text-lg font-bold text-white mb-1">
                      {{ activeScript?.title || 'Synthesized Podcast' }}
                    </h4>
                    <p class="text-xs text-govuk-grey-3 leading-relaxed">
                      Format: WAV | Rate: 24kHz Stereo | Speakers: bf_alice & bm_george
                    </p>
                  </div>
                </div>

                <div class="flex items-center gap-3 w-full md:w-auto justify-end">
                  <!-- Custom Web Player Controls -->
                  <button 
                    @click="togglePlay" 
                    class="bg-govuk-blue hover:bg-[#154f83] text-white p-3 font-bold rounded-full transition-all shadow-md active:scale-95"
                  >
                    <Pause v-if="isPlaying" class="h-6 w-6" />
                    <Play v-else class="h-6 w-6" />
                  </button>

                  <a 
                    :href="audioUrl" 
                    download 
                    class="bg-govuk-grey-1 hover:bg-govuk-grey-2 text-white p-3 font-bold rounded-full transition-all shadow-md"
                    title="Download WAV file"
                  >
                    <Download class="h-6 w-6" />
                  </a>
                </div>

                <!-- Hidden audio tag -->
                <audio 
                  ref="audioRef" 
                  :src="audioUrl" 
                  @ended="isPlaying = false"
                  class="hidden"
                ></audio>
              </div>

            </div>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>
