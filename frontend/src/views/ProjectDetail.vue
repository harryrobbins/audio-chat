<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { marked } from 'marked'
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

import { 
  ArrowLeft, FileText, UploadCloud, BookOpen, Brain, 
  Sparkles, Music, Play, Pause, Download, Trash2, 
  PlusCircle, Save, Loader, AlertTriangle, Search, CheckCircle, Users
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const projectId = ref(Number(route.params.id))
const API_BASE = 'http://localhost:8000'

// Tabs with URL persistence
const validTabs = ['documents', 'wiki', 'script', 'audio']
const getInitialTab = () => {
  const queryTab = route.query.tab
  if (queryTab && typeof queryTab === 'string' && validTabs.includes(queryTab)) {
    return queryTab
  }
  return 'documents'
}
const activeTab = ref(getInitialTab())

watch(activeTab, (newTab) => {
  if (route.query.tab !== newTab) {
    router.replace({ query: { ...route.query, tab: newTab } })
  }
})

watch(() => route.query.tab, (newTab) => {
  if (newTab && typeof newTab === 'string' && validTabs.includes(newTab)) {
    activeTab.value = newTab
  }
})

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
const isDragging = ref(false)
const dragCounter = ref(0)
const fileInput = ref<HTMLInputElement | null>(null)


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
const audioLogs = ref<string[]>([])
const generatedAudio = ref<any>(null)
const audioUrl = ref('')
const audioRef = ref<HTMLAudioElement | null>(null)
const isPlaying = ref(false)

// Console Refs for Auto-scrolling
const kbConsoleRef = ref<HTMLElement | null>(null)
const scriptConsoleRef = ref<HTMLElement | null>(null)
const audioConsoleRef = ref<HTMLElement | null>(null)

watch(kbLogs, () => {
  nextTick(() => {
    if (kbConsoleRef.value) {
      kbConsoleRef.value.scrollTop = kbConsoleRef.value.scrollHeight
    }
  })
}, { deep: true })

watch(scriptLogs, () => {
  nextTick(() => {
    if (scriptConsoleRef.value) {
      scriptConsoleRef.value.scrollTop = scriptConsoleRef.value.scrollHeight
    }
  })
}, { deep: true })

watch(audioLogs, () => {
  nextTick(() => {
    if (audioConsoleRef.value) {
      audioConsoleRef.value.scrollTop = audioConsoleRef.value.scrollHeight
    }
  })
}, { deep: true })

// Settings panel & configurations
const settingsExpanded = ref(false)
const selectedAudioModel = ref('kokoro-82m')

// Kokoro
const kokoroSpeed = ref(1.0)
const kokoroHostVoice = ref('bf_alice')
const kokoroGuestVoice = ref('bm_george')

// Pocket TTS
const pocketSpeed = ref(1.0)
const pocketHostVoice = ref('alba')
const pocketGuestVoice = ref('marius')

// Gemini Flash
const geminiSpeed = ref(1.0)
const geminiHostVoice = ref('Aoede')
const geminiGuestVoice = ref('Charon')

// Dynamic VOICE_MAP configuration mapping voices to default names and genders
const VOICE_MAP = {
  // Kokoro-82M
  "bf_alice": { name: "Alice", gender: "female" },
  "bf_emma": { name: "Emma", gender: "female" },
  "bm_george": { name: "George", gender: "male" },
  "af_heart": { name: "Heart", gender: "female" },
  "af_bella": { name: "Bella", gender: "female" },
  "am_adam": { name: "Adam", gender: "male" },
  "am_michael": { name: "Michael", gender: "male" },
  
  // Pocket TTS / gTTS
  "alba": { name: "Alba", gender: "female" },
  "fantine": { name: "Fantine", gender: "female" },
  "cosette": { name: "Cosette", gender: "female" },
  "marius": { name: "Marius", gender: "male" },
  "javert": { name: "Javert", gender: "male" },
  "jean": { name: "Jean", gender: "male" },
  "en": { name: "US Host", gender: "female" },
  "en-uk": { name: "UK Host", gender: "female" },
  "en-au": { name: "AU Host", gender: "female" },
  "es": { name: "Spanish Host", gender: "female" },
  "fr": { name: "French Host", gender: "female" },
  
  // Gemini Flash TTS
  "Aoede": { name: "Aoede", gender: "female" },
  "Kore": { name: "Kore", gender: "female" },
  "Puck": { name: "Puck", gender: "male" },
  "Charon": { name: "Charon", gender: "male" },
  "Fenrir": { name: "Fenrir", gender: "male" }
}

const speaker1Name = ref('')
const speaker2Name = ref('')
const speaker1Overridden = ref(false)
const speaker2Overridden = ref(false)

const activeHostVoice = computed(() => {
  if (selectedAudioModel.value === 'kokoro-82m') return kokoroHostVoice.value
  if (selectedAudioModel.value === 'pocket-tts') return pocketHostVoice.value
  if (selectedAudioModel.value === 'gemini-flash-tts') return geminiHostVoice.value
  return 'bf_alice'
})

const activeGuestVoice = computed(() => {
  if (selectedAudioModel.value === 'kokoro-82m') return kokoroGuestVoice.value
  if (selectedAudioModel.value === 'pocket-tts') return pocketGuestVoice.value
  if (selectedAudioModel.value === 'gemini-flash-tts') return geminiGuestVoice.value
  return 'bm_george'
})

const hostVoiceMeta = computed(() => {
  return VOICE_MAP[activeHostVoice.value] || { name: 'Host', gender: 'female' }
})

const guestVoiceMeta = computed(() => {
  return VOICE_MAP[activeGuestVoice.value] || { name: 'Guest', gender: 'male' }
})

watch(activeHostVoice, (newVoice) => {
  if (!speaker1Overridden.value) {
    speaker1Name.value = VOICE_MAP[newVoice]?.name || 'Speaker 1'
  }
}, { immediate: true })

watch(activeGuestVoice, (newVoice) => {
  if (!speaker2Overridden.value) {
    speaker2Name.value = VOICE_MAP[newVoice]?.name || 'Speaker 2'
  }
}, { immediate: true })

// Complete audios comparison list for active script
const scriptAudios = ref<any[]>([])

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

const getDocTitle = (docId: number) => {
  const doc = documents.value.find((d: any) => d.id === docId)
  return doc ? doc.title : `Doc #${docId}`
}

const getFactDocIds = (fact: any) => {
  if (fact.document_ids) {
    return fact.document_ids.split(',').map((idStr: string) => parseInt(idStr.trim(), 10)).filter((id: number) => !isNaN(id))
  }
  return fact.document_id ? [fact.document_id] : []
}

const viewDocumentSource = (docId: number) => {
  const doc = documents.value.find((d: any) => d.id === docId)
  if (doc) {
    selectedDoc.value = doc
    activeTab.value = 'documents'
    nextTick(() => {
      const drawer = document.getElementById('selected-doc-drawer')
      if (drawer) {
        drawer.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    })
  }
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

const handleDeleteDoc = async (docId: number) => {
  if (!confirm('Are you sure you want to delete this document? All facts extracted from this document will also be removed.')) return
  try {
    await axios.delete(`${API_BASE}/projects/${projectId.value}/documents/${docId}`)
    if (selectedDoc.value && selectedDoc.value.id === docId) {
      selectedDoc.value = null
    }
    await fetchDocuments()
  } catch (err) {
    console.error(err)
    alert('Failed to delete document')
  }
}

const triggerFileInput = () => {
  fileInput.value?.click()
}

const handleDragEnter = (e: DragEvent) => {
  e.preventDefault()
  dragCounter.value++
  if (dragCounter.value === 1) {
    isDragging.value = true
  }
}

const handleDragLeave = (e: DragEvent) => {
  e.preventDefault()
  dragCounter.value--
  if (dragCounter.value <= 0) {
    dragCounter.value = 0
    isDragging.value = false
  }
}

const handleDragOver = (e: DragEvent) => {
  e.preventDefault()
}

const handleFileDrop = async (e: DragEvent) => {
  e.preventDefault()
  isDragging.value = false
  dragCounter.value = 0
  const files = e.dataTransfer?.files
  if (!files || files.length === 0) return
  await uploadFiles(files)
}

const handleFileSelect = async (e: Event) => {
  const files = (e.target as HTMLInputElement).files
  if (!files || files.length === 0) return
  await uploadFiles(files)
}

const readFileAsText = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => resolve(e.target?.result as string || '')
    reader.onerror = (e) => reject(e)
    reader.readAsText(file)
  })
}

const extractTextFromPDF = async (arrayBuffer: ArrayBuffer): Promise<string> => {
  const pdfjsLib = await import('pdfjs-dist')
  pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker
  
  const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer })
  const pdf = await loadingTask.promise
  let fullText = ''
  
  for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
    const page = await pdf.getPage(pageNum)
    const textContent = await page.getTextContent()
    const pageText = textContent.items
      .map((item: any) => item.str)
      .join(' ')
    fullText += pageText + '\n\n'
  }
  return fullText
}

const extractTextFromDocx = async (arrayBuffer: ArrayBuffer): Promise<string> => {
  const mammoth = await import('mammoth')
  const result = await mammoth.extractRawText({ arrayBuffer })
  return result.value
}

const uploadFiles = async (files: FileList) => {
  uploadingDoc.value = true
  try {
    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      let extractedText = ''
      
      if (file.name.endsWith('.pdf')) {
        try {
          const arrayBuffer = await file.arrayBuffer()
          extractedText = await extractTextFromPDF(arrayBuffer)
        } catch (pdfErr) {
          console.error('Error parsing PDF:', pdfErr)
          alert(`Failed to extract text from PDF "${file.name}". Details: ${pdfErr}`)
          continue
        }
      } else if (file.name.endsWith('.docx')) {
        try {
          const arrayBuffer = await file.arrayBuffer()
          extractedText = await extractTextFromDocx(arrayBuffer)
        } catch (docxErr) {
          console.error('Error parsing DOCX:', docxErr)
          alert(`Failed to extract text from DOCX "${file.name}". Details: ${docxErr}`)
          continue
        }
      } else if (
        file.type.startsWith('text/') || 
        file.name.endsWith('.txt') || 
        file.name.endsWith('.md') || 
        file.name.endsWith('.markdown') ||
        file.name.endsWith('.json') ||
        file.name.endsWith('.csv')
      ) {
        try {
          extractedText = await readFileAsText(file)
        } catch (txtErr) {
          console.error('Error reading text file:', txtErr)
          alert(`Failed to read file "${file.name}". Details: ${txtErr}`)
          continue
        }
      } else {
        alert(`File "${file.name}" is not supported. Please upload .txt, .md, .pdf, or .docx files.`)
        continue
      }
      
      if (!extractedText.trim()) {
        alert(`File "${file.name}" was parsed but no text content was found.`)
        continue
      }
      
      // Upload the extracted text to the backend document processing endpoint
      await axios.post(`${API_BASE}/projects/${projectId.value}/documents/process`, {
        raw_text: extractedText,
        filename_hint: file.name
      })
      
      // Immediately refresh the list as each document completes processing
      await fetchDocuments()
    }
  } catch (err) {
    console.error(err)
    alert('Failed to process and upload document(s).')
  } finally {
    uploadingDoc.value = false
    await fetchDocuments()
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
    scriptAudios.value = fullScript.audios || []
    if (scriptAudios.value.length > 0) {
      // Find the latest audio (highest id)
      const sortedAudios = [...scriptAudios.value].sort((a, b) => b.id - a.id)
      generatedAudio.value = sortedAudios[0]
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
  audioLogs.value = []
  audioLogs.value.push('Preparing audio compilers...')
  try {
    let settingsObj = {}
    if (selectedAudioModel.value === 'kokoro-82m') {
      settingsObj = {
        speed: kokoroSpeed.value,
        voice_host: kokoroHostVoice.value,
        voice_guest: kokoroGuestVoice.value,
        speaker_1_name: speaker1Name.value,
        speaker_2_name: speaker2Name.value
      }
    } else if (selectedAudioModel.value === 'pocket-tts') {
      settingsObj = {
        speed: pocketSpeed.value,
        voice_host: pocketHostVoice.value,
        voice_guest: pocketGuestVoice.value,
        speaker_1_name: speaker1Name.value,
        speaker_2_name: speaker2Name.value
      }
    } else if (selectedAudioModel.value === 'gemini-flash-tts') {
      settingsObj = {
        speed: geminiSpeed.value,
        voice_host: geminiHostVoice.value,
        voice_guest: geminiGuestVoice.value,
        speaker_1_name: speaker1Name.value,
        speaker_2_name: speaker2Name.value
      }
    }

    await runStream(
      `${API_BASE}/projects/scripts/${selectedScriptId.value}/generate-audio`,
      {
        model_name: selectedAudioModel.value,
        settings: settingsObj
      },
      async (data) => {
        if (data.status) {
          audioProgress.value = data.status
          audioLogs.value.push(data.status)
        }
        if (data.done) {
          generatedAudio.value = data
          audioUrl.value = `${API_BASE}${data.download_url}`
          audioProgress.value = 'Audio synthesis complete!'
          audioLogs.value.push('Audio synthesis complete!')
          await fetchScripts() // refresh script list to link audio
          if (selectedScriptId.value) {
            await handleReadScript(selectedScriptId.value)
          }
        }
      }
    )
  } catch (err: any) {
    console.error(err)
    const errMsg = `[ERROR] Synthesis failed: ${err.message}`
    audioProgress.value = errMsg
    audioLogs.value.push(errMsg)
  } finally {
    synthesizingAudio.value = false
  }
}

const playAudioRecord = (audio: any) => {
  generatedAudio.value = audio
  audioUrl.value = `${API_BASE}/projects/audio/${audio.id}`
  isPlaying.value = false
  setTimeout(() => {
    if (audioRef.value) {
      audioRef.value.play()
      isPlaying.value = true
    }
  }, 100)
}

const handleDeleteAudio = async (audioId: number) => {
  if (!confirm('Are you sure you want to delete this generated audio comparison file?')) return
  try {
    await axios.delete(`${API_BASE}/projects/audio/${audioId}`)
    // If the deleted audio was currently loaded in player, clear player
    if (generatedAudio.value && generatedAudio.value.id === audioId) {
      isPlaying.value = false
      generatedAudio.value = null
      audioUrl.value = ''
    }
    // Refresh script detail and audio list
    if (selectedScriptId.value) {
      await handleReadScript(selectedScriptId.value)
    }
  } catch (err: any) {
    console.error('Failed to delete audio record:', err)
    alert(`Failed to delete audio record: ${err.message}`)
  }
}

const handleDeleteScript = async (scriptId: number) => {
  if (!confirm('Are you sure you want to delete this generated podcast script? All associated audio comparison files will also be permanently deleted.')) return
  try {
    await axios.delete(`${API_BASE}/projects/scripts/${scriptId}`)
    
    // If the deleted script was currently selected, clear active script states
    if (selectedScriptId.value === scriptId) {
      selectedScriptId.value = null
      activeScript.value = null
      editedLines.value = []
      generatedAudio.value = null
      audioUrl.value = ''
    }
    
    // Refresh scripts list
    await fetchScripts()
    
    alert('Script deleted successfully!')
  } catch (err: any) {
    console.error('Failed to delete script:', err)
    alert(`Failed to delete script: ${err.message}`)
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

const renderedMarkdown = computed(() => {
  if (!selectedDoc.value) return ''
  try {
    return marked.parse(selectedDoc.value.content)
  } catch (e) {
    console.error(e)
    return selectedDoc.value.content
  }
})


watch(selectedScriptId, (newId) => {
  speaker1Overridden.value = false
  speaker2Overridden.value = false
  speaker1Name.value = hostVoiceMeta.value.name
  speaker2Name.value = guestVoiceMeta.value.name
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
        <div 
          v-if="activeTab === 'documents'" 
          class="relative min-h-[500px]"
          @dragenter="handleDragEnter"
          @dragover="handleDragOver"
          @dragleave="handleDragLeave"
          @drop="handleFileDrop"
        >
          <!-- Full-tab Drag over Overlay with premium glassmorphism styling -->
          <div 
            v-if="isDragging"
            class="absolute inset-0 bg-govuk-blue/10 border-4 border-dashed border-govuk-blue z-50 flex flex-col items-center justify-center backdrop-blur-[2px] transition-all duration-200 pointer-events-none"
          >
            <div class="bg-govuk-white p-8 rounded-lg shadow-lg border-2 border-govuk-blue flex flex-col items-center max-w-sm text-center">
              <UploadCloud class="h-16 w-16 text-govuk-blue mb-4 animate-bounce" />
              <h3 class="govuk-heading-m text-govuk-blue m-0">Drop Files Anywhere</h3>
              <p class="text-sm text-govuk-grey-1 mt-2 leading-relaxed">
                Release your files to automatically extract text, clean content using Gemini, and integrate them into your project.
              </p>
              <span class="text-xs text-govuk-grey-2 mt-2 bg-govuk-grey-4 px-3 py-1 rounded">
                Supports .txt, .md, .pdf, .docx
              </span>
            </div>
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <!-- Upload form & Drag-and-Drop Zone -->
          <div class="lg:col-span-1 border-4 border-govuk-grey-3 p-6 bg-govuk-grey-4 flex flex-col gap-6">
            <!-- Drag and Drop Zone -->
            <div>
              <h3 class="govuk-heading-s flex items-center gap-2 mb-4">
                <UploadCloud class="h-5 w-5 text-govuk-blue" />
                Upload via Drag &amp; Drop
              </h3>
              <div 
                class="border-4 border-dashed p-6 text-center transition-all cursor-pointer flex flex-col items-center justify-center min-h-[160px] bg-govuk-white hover:border-govuk-blue"
                :class="isDragging ? 'border-govuk-blue bg-blue-50/10 scale-[1.02]' : 'border-govuk-grey-3'"
                @click="triggerFileInput"
              >
                <input 
                  type="file" 
                  ref="fileInput" 
                  class="hidden" 
                  multiple
                  accept=".txt,.md,.markdown,.json,.csv,.pdf,.docx"
                  @change="handleFileSelect"
                />
                <UploadCloud class="h-10 w-10 text-govuk-blue mb-2 animate-bounce" v-if="isDragging" />
                <UploadCloud class="h-10 w-10 text-govuk-grey-2 mb-2" v-else />
                <p class="text-sm font-bold text-govuk-black">
                  Drag &amp; Drop documents here
                </p>
                <p class="text-xs text-govuk-grey-2 mt-1">
                  or click to select from files
                </p>
                <p class="text-[10px] text-govuk-grey-2 mt-3 bg-govuk-grey-4 px-2 py-1 rounded">
                  Supports .txt, .md, .pdf, .docx
                </p>
              </div>

            </div>

            <!-- Visual Divider -->
            <div class="relative flex py-1 items-center">
              <div class="flex-grow border-t border-govuk-grey-3"></div>
              <span class="flex-shrink mx-4 text-govuk-grey-2 text-[10px] font-bold tracking-wider">OR PASTE CONTENT</span>
              <div class="flex-grow border-t border-govuk-grey-3"></div>
            </div>

            <!-- Manual Form -->
            <div>
              <h3 class="govuk-heading-s flex items-center gap-2 mb-4">
                <FileText class="h-5 w-5 text-govuk-blue" />
                Manual Document Entry
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
                    rows="8" 
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
                <div class="flex items-center gap-2" @click.stop>
                  <button 
                    @click="selectedDoc = doc" 
                    class="govuk-button-secondary py-1 px-3 text-xs font-bold"
                  >
                    View File
                  </button>
                  <button 
                    @click="handleDeleteDoc(doc.id)" 
                    class="bg-govuk-red/10 hover:bg-govuk-red/20 text-govuk-red p-1.5 rounded transition-colors flex items-center justify-center border border-govuk-red/20"
                    title="Delete document"
                  >
                    <Trash2 class="h-3.5 w-3.5" />
                  </button>
                </div>
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
              <div class="bg-govuk-grey-4 p-4 max-h-[300px] overflow-y-auto rounded text-sm leading-relaxed font-sans markdown-content" v-html="renderedMarkdown">
              </div>

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
              <div ref="kbConsoleRef" class="bg-govuk-black text-govuk-green p-4 font-mono text-xs rounded-md shadow-inner flex-grow max-h-[300px] overflow-y-auto leading-relaxed border-2 border-govuk-grey-3">
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
                <div class="text-[10px] text-govuk-grey-2 flex flex-wrap justify-between items-center gap-2 pt-2 mt-2 border-t border-govuk-grey-4">
                  <span>REF: Fact #{{ fact.id }}</span>
                  <div class="flex flex-wrap gap-1.5 items-center">
                    <span class="font-bold text-govuk-grey-1 mr-1">Sources:</span>
                    <button 
                      v-for="docId in getFactDocIds(fact)" 
                      :key="docId"
                      @click="viewDocumentSource(docId)"
                      class="px-2 py-0.5 bg-govuk-blue/10 hover:bg-govuk-blue/20 text-govuk-blue font-bold rounded border border-govuk-blue/20 cursor-pointer transition-colors max-w-[150px] truncate text-[10px]"
                      :title="'View source: ' + getDocTitle(docId)"
                    >
                      {{ getDocTitle(docId) }}
                    </button>
                  </div>
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
              <div ref="scriptConsoleRef" class="bg-govuk-black text-govuk-green p-4 font-mono text-xs rounded-md shadow-inner flex-grow max-h-[300px] overflow-y-auto leading-relaxed border-2 border-govuk-grey-3">
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
                  <button 
                    v-if="!isEditing" 
                    @click="handleDeleteScript(selectedScriptId!)" 
                    class="bg-govuk-red hover:bg-[#b01616] text-white py-1.5 px-4 text-sm font-bold flex items-center gap-1.5 transition-all rounded"
                  >
                    <Trash2 class="h-4 w-4" />
                    <span>Delete Script</span>
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
          <div class="flex justify-between items-center border-b border-govuk-grey-3 pb-3">
            <h3 class="govuk-heading-m m-0">Podcast Synthesis & Comparison Workspace</h3>
            <span class="bg-govuk-blue text-white text-[11px] px-2 py-0.5 font-bold uppercase rounded flex items-center gap-1">
              <Sparkles class="h-3 w-3" /> Multi-Model Audio Studio
            </span>
          </div>
          
          <div v-if="scriptsList.length === 0" class="border-2 border-dashed p-8 text-center text-govuk-grey-2">
            No podcast scripts available. Create a script in the Workspace tab first before compiling speech.
          </div>

          <div v-else class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- Control Synthesis Panel -->
            <div class="lg:col-span-1 border-4 border-govuk-grey-3 p-6 bg-govuk-grey-4 flex flex-col justify-between h-fit">
              <div>
                <label class="block text-sm font-bold mb-2">Select Target Script:</label>
                <select v-model="selectedScriptId" class="govuk-input text-sm mb-4">
                  <option v-for="s in scriptsList" :key="s.id" :value="s.id">
                    {{ s.title }}
                  </option>
                </select>

                <!-- Configure Podcast Speakers Panel -->
                <div v-if="personasList.length > 0" class="mb-4 border-2 border-govuk-black p-4 bg-govuk-white rounded">
                  <h4 class="govuk-heading-s mb-3 flex items-center gap-1.5 text-govuk-black border-b border-govuk-grey-3 pb-2">
                    <Users class="h-4 w-4 text-govuk-blue" />
                    Configure Podcast Speakers
                  </h4>
                  
                  <div class="space-y-4">
                    <!-- Speaker 1 -->
                    <div class="border-b border-govuk-grey-3 pb-3 last:border-0 last:pb-0">
                      <div class="flex justify-between items-center mb-1">
                        <span class="text-xs font-bold text-govuk-black">
                          Speaker 1 ({speaker_1}) ({{ hostVoiceMeta.gender }})
                        </span>
                        <span class="text-[10px] text-govuk-grey-2 italic">Role: {{ personasList[0]?.role || 'Host' }}</span>
                      </div>
                      <div class="text-[11px] text-govuk-grey-1 mb-2 leading-tight">
                        {{ personasList[0]?.description }}
                      </div>
                      <div>
                        <label class="block text-[10px] font-bold text-govuk-grey-1 mb-0.5">Customize Name:</label>
                        <input 
                          type="text" 
                          v-model="speaker1Name" 
                          @input="speaker1Overridden = true" 
                          placeholder="e.g. Alice"
                          class="govuk-input text-xs py-1 px-2 border-2 border-govuk-black bg-white" 
                        />
                        <span class="text-[9px] text-govuk-grey-2 mt-0.5 block" v-if="!speaker1Overridden">
                          Defaulting to chosen voice: <strong>{{ hostVoiceMeta.name }}</strong>
                        </span>
                        <span class="text-[9px] text-govuk-blue mt-0.5 block hover:underline cursor-pointer" v-else @click="speaker1Overridden = false; speaker1Name = hostVoiceMeta.name">
                          Reset to default ({{ hostVoiceMeta.name }})
                        </span>
                      </div>
                    </div>

                    <!-- Speaker 2 -->
                    <div>
                      <div class="flex justify-between items-center mb-1">
                        <span class="text-xs font-bold text-govuk-black">
                          Speaker 2 ({speaker_2}) ({{ guestVoiceMeta.gender }})
                        </span>
                        <span class="text-[10px] text-govuk-grey-2 italic">Role: {{ personasList[1]?.role || 'Guest' }}</span>
                      </div>
                      <div class="text-[11px] text-govuk-grey-1 mb-2 leading-tight">
                        {{ personasList[1]?.description }}
                      </div>
                      <div>
                        <label class="block text-[10px] font-bold text-govuk-grey-1 mb-0.5">Customize Name:</label>
                        <input 
                          type="text" 
                          v-model="speaker2Name" 
                          @input="speaker2Overridden = true" 
                          placeholder="e.g. George"
                          class="govuk-input text-xs py-1 px-2 border-2 border-govuk-black bg-white" 
                        />
                        <span class="text-[9px] text-govuk-grey-2 mt-0.5 block" v-if="!speaker2Overridden">
                          Defaulting to chosen voice: <strong>{{ guestVoiceMeta.name }}</strong>
                        </span>
                        <span class="text-[9px] text-govuk-blue mt-0.5 block hover:underline cursor-pointer" v-else @click="speaker2Overridden = false; speaker2Name = guestVoiceMeta.name">
                          Reset to default ({{ guestVoiceMeta.name }})
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- TTS Settings Panel Trigger -->
                <button 
                  @click="settingsExpanded = !settingsExpanded"
                  class="flex items-center justify-between w-full p-3 mb-4 bg-govuk-white border-2 border-govuk-black hover:bg-govuk-grey-4 transition-all rounded font-bold text-xs"
                >
                  <span class="flex items-center gap-2">
                    <Sparkles class="h-4 w-4 text-govuk-blue animate-spin" v-if="settingsExpanded" />
                    <Music class="h-4 w-4 text-govuk-grey-2" v-else />
                    Configure Audio Generation
                  </span>
                  <span>{{ settingsExpanded ? '▲ Hide' : '▼ Expand Settings' }}</span>
                </button>

                <!-- Settings panel -->
                <div v-if="settingsExpanded" class="border-2 border-govuk-black p-4 mb-4 bg-govuk-white space-y-4 rounded shadow-inner">
                  <!-- Model Selection Tabs -->
                  <div class="flex border-b border-govuk-grey-3 mb-3">
                    <button 
                      @click="selectedAudioModel = 'kokoro-82m'" 
                      :class="['flex-1 pb-2 text-xs font-bold text-center border-b-4 transition-all', selectedAudioModel === 'kokoro-82m' ? 'border-govuk-blue text-govuk-blue' : 'border-transparent text-govuk-grey-2']"
                    >
                      Kokoro 82M
                    </button>
                    <button 
                      @click="selectedAudioModel = 'pocket-tts'" 
                      :class="['flex-1 pb-2 text-xs font-bold text-center border-b-4 transition-all', selectedAudioModel === 'pocket-tts' ? 'border-govuk-red text-govuk-red' : 'border-transparent text-govuk-grey-2']"
                    >
                      Pocket TTS
                    </button>
                    <button 
                      @click="selectedAudioModel = 'gemini-flash-tts'" 
                      :class="['flex-1 pb-2 text-xs font-bold text-center border-b-4 transition-all', selectedAudioModel === 'gemini-flash-tts' ? 'border-purple-600 text-purple-600' : 'border-transparent text-govuk-grey-2']"
                    >
                      Gemini Flash
                    </button>
                  </div>

                  <!-- Model specific inputs -->
                  <div v-if="selectedAudioModel === 'kokoro-82m'" class="space-y-3">
                    <span class="block text-[10px] text-govuk-grey-2 italic">Local deep learning neural network TTS. Best sound quality.</span>
                    
                    <div>
                      <label class="block text-xs font-bold mb-1">Synthesis Speed: {{ kokoroSpeed }}x</label>
                      <input type="range" v-model.number="kokoroSpeed" min="0.5" max="2.0" step="0.1" class="w-full h-1 bg-govuk-grey-3 rounded cursor-pointer accent-govuk-blue" />
                    </div>

                    <div>
                      <label class="block text-xs font-bold mb-1">Host Voice (Speaker 1)</label>
                      <select v-model="kokoroHostVoice" class="w-full text-xs p-1.5 border border-govuk-black bg-white">
                        <option value="bf_alice">bf_alice (British Female)</option>
                        <option value="bf_emma">bf_emma (British Female)</option>
                        <option value="bm_george">bm_george (British Male)</option>
                        <option value="af_heart">af_heart (American Female)</option>
                        <option value="af_bella">af_bella (American Female)</option>
                        <option value="am_adam">am_adam (American Male)</option>
                        <option value="am_michael">am_michael (American Male)</option>
                      </select>
                    </div>

                    <div>
                      <label class="block text-xs font-bold mb-1">Guest Voice (Speaker 2)</label>
                      <select v-model="kokoroGuestVoice" class="w-full text-xs p-1.5 border border-govuk-black bg-white">
                        <option value="bm_george">bm_george (British Male)</option>
                        <option value="bf_alice">bf_alice (British Female)</option>
                        <option value="bf_emma">bf_emma (British Female)</option>
                        <option value="af_heart">af_heart (American Female)</option>
                        <option value="af_bella">af_bella (American Female)</option>
                        <option value="am_adam">am_adam (American Male)</option>
                        <option value="am_michael">am_michael (American Male)</option>
                      </select>
                    </div>
                  </div>

                  <div v-if="selectedAudioModel === 'pocket-tts'" class="space-y-3">
                    <span class="block text-[10px] text-govuk-red italic">Kyutai CPU-efficient model with built-in voices. Safe offline gTTS fallback.</span>
                    
                    <div>
                      <label class="block text-xs font-bold mb-1">Synthesis Speed: {{ pocketSpeed }}x</label>
                      <input type="range" v-model.number="pocketSpeed" min="0.5" max="2.0" step="0.1" class="w-full h-1 bg-govuk-grey-3 rounded cursor-pointer accent-govuk-red" />
                    </div>

                    <div>
                      <label class="block text-xs font-bold mb-1">Host Voice / Accent</label>
                      <select v-model="pocketHostVoice" class="w-full text-xs p-1.5 border border-govuk-black bg-white">
                        <option value="alba">alba (Kyutai Native)</option>
                        <option value="marius">marius (Kyutai Native)</option>
                        <option value="javert">javert (Kyutai Native)</option>
                        <option value="jean">jean (Kyutai Native)</option>
                        <option value="fantine">fantine (Kyutai Native)</option>
                        <option value="en">gTTS US English</option>
                        <option value="en-uk">gTTS UK English</option>
                        <option value="en-au">gTTS Australia English</option>
                        <option value="es">gTTS Spanish</option>
                        <option value="fr">gTTS French</option>
                      </select>
                    </div>

                    <div>
                      <label class="block text-xs font-bold mb-1">Guest Voice / Accent</label>
                      <select v-model="pocketGuestVoice" class="w-full text-xs p-1.5 border border-govuk-black bg-white">
                        <option value="marius">marius (Kyutai Native)</option>
                        <option value="alba">alba (Kyutai Native)</option>
                        <option value="javert">javert (Kyutai Native)</option>
                        <option value="jean">jean (Kyutai Native)</option>
                        <option value="cosette">cosette (Kyutai Native)</option>
                        <option value="en-uk">gTTS UK English</option>
                        <option value="en">gTTS US English</option>
                        <option value="en-au">gTTS Australia English</option>
                        <option value="es">gTTS Spanish</option>
                        <option value="fr">gTTS French</option>
                      </select>
                    </div>
                  </div>

                  <div v-if="selectedAudioModel === 'gemini-flash-tts'" class="space-y-3">
                    <span class="block text-[10px] text-purple-600 italic">Cloud multimodal voice synthesizer. Exquisite multi-speaker dialogue.</span>
                    
                    <div>
                      <label class="block text-xs font-bold mb-1">Synthesis Speed: {{ geminiSpeed }}x</label>
                      <input type="range" v-model.number="geminiSpeed" min="0.5" max="2.0" step="0.1" class="w-full h-1 bg-govuk-grey-3 rounded cursor-pointer accent-purple-600" />
                    </div>

                    <div>
                      <label class="block text-xs font-bold mb-1">Host Voice (Speaker 1)</label>
                      <select v-model="geminiHostVoice" class="w-full text-xs p-1.5 border border-govuk-black bg-white">
                        <option value="Aoede">Aoede (Female)</option>
                        <option value="Kore">Kore (Female)</option>
                        <option value="Puck">Puck (Male)</option>
                        <option value="Charon">Charon (Male)</option>
                        <option value="Fenrir">Fenrir (Male)</option>
                      </select>
                    </div>

                    <div>
                      <label class="block text-xs font-bold mb-1">Guest Voice (Speaker 2)</label>
                      <select v-model="geminiGuestVoice" class="w-full text-xs p-1.5 border border-govuk-black bg-white">
                        <option value="Charon">Charon (Male)</option>
                        <option value="Puck">Puck (Male)</option>
                        <option value="Fenrir">Fenrir (Male)</option>
                        <option value="Aoede">Aoede (Female)</option>
                        <option value="Kore">Kore (Female)</option>
                      </select>
                    </div>
                  </div>
                </div>
              </div>

              <button 
                @click="handleGenerateAudio" 
                :disabled="synthesizingAudio || !selectedScriptId" 
                class="govuk-button w-full flex items-center justify-center gap-2 mt-4"
              >
                <Loader v-if="synthesizingAudio" class="h-5 w-5 animate-spin" />
                <Music class="h-5 w-5" v-else />
                <span>Generate Podcast Audio</span>
              </button>
            </div>

            <!-- Progress Details / Audio Output Console -->
            <div class="lg:col-span-2 space-y-4 flex flex-col justify-between">
              <div>
                <h4 class="govuk-heading-s mb-2">Synthesis Progress Log</h4>
                <div ref="audioConsoleRef" class="bg-govuk-black text-govuk-green p-4 font-mono text-xs rounded-md shadow-inner min-h-[100px] max-h-[140px] overflow-y-auto leading-relaxed border-2 border-govuk-grey-3 mb-4">
                  <div v-for="(log, idx) in audioLogs" :key="idx" class="mb-1">&gt; {{ log }}</div>
                  <div v-if="synthesizingAudio" class="flex items-center gap-2 mt-2">
                    <span class="h-2 w-2 rounded-full bg-govuk-green animate-ping"></span>
                    <span class="text-xs italic text-govuk-grey-3">Synthesizing audio nodes on the server, please wait...</span>
                  </div>
                  <div v-else-if="audioLogs.length === 0" class="text-govuk-grey-2 italic">
                    Waiting to synthesize speech blocks. Open Settings above to configure voices.
                  </div>
                </div>
              </div>

              <!-- Audio Player Card -->
              <div 
                v-if="audioUrl" 
                class="bg-govuk-black border-4 border-govuk-blue text-white p-6 shadow-xl flex flex-col md:flex-row items-center justify-between gap-6 transition-all duration-300 rounded mb-4"
              >
                <div class="flex items-center gap-4 flex-grow min-w-0">
                  <div class="bg-govuk-blue p-3.5 text-white rounded-full flex-shrink-0">
                    <Music class="h-7 w-7 animate-pulse" />
                  </div>
                  <div class="min-w-0">
                    <h4 class="text-lg font-bold text-white mb-1 truncate">
                      {{ activeScript?.title || 'Synthesized Podcast' }}
                    </h4>
                    <p class="text-xs text-govuk-grey-3 leading-relaxed truncate">
                      Active: ID #{{ generatedAudio?.id }} | Model: <span class="capitalize text-govuk-blue font-bold">{{ generatedAudio?.model_name }}</span> | Host: {{ generatedAudio?.settings?.voice_host || 'bf_alice' }} (Speed: {{ generatedAudio?.settings?.speed || '1.0' }}x)
                    </p>
                  </div>
                </div>

                <div class="flex items-center gap-3 w-full md:w-auto justify-end flex-shrink-0">
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
                    class="bg-govuk-grey-1 hover:bg-govuk-grey-2 text-white p-3 font-bold rounded-full transition-all shadow-md flex items-center justify-center"
                    title="Download WAV file"
                  >
                    <Download class="h-6 w-6" />
                  </a>
                </div>

                <audio 
                  ref="audioRef" 
                  :src="audioUrl" 
                  @ended="isPlaying = false"
                  class="hidden"
                ></audio>
              </div>
            </div>
          </div>

          <!-- Comparison Section -->
          <div class="border-t-4 border-govuk-grey-3 pt-6" v-if="scriptsList.length > 0">
            <h3 class="govuk-heading-m mb-4">Generated Audio Comparison Studio</h3>
            
            <div v-if="scriptAudios.length === 0" class="border-2 border-dashed p-8 text-center text-govuk-grey-2">
              No audio variations compiled for this script yet. Adjust configurations in the panel above and generate to compare results!
            </div>
            
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <div 
                v-for="audio in scriptAudios" 
                :key="audio.id" 
                :class="['border-4 p-4 flex flex-col justify-between transition-all rounded bg-white shadow-sm', generatedAudio?.id === audio.id ? 'border-govuk-blue shadow-md' : 'border-govuk-grey-3']"
              >
                <div>
                  <div class="flex justify-between items-center mb-3">
                    <span 
                      :class="['text-[10px] px-2 py-0.5 font-bold uppercase rounded', 
                        audio.model_name === 'kokoro-82m' ? 'bg-blue-100 text-blue-800' :
                        audio.model_name === 'pocket-tts' ? 'bg-red-100 text-red-800' : 'bg-purple-100 text-purple-800']"
                    >
                      {{ audio.model_name }}
                    </span>
                    <span class="text-[10px] text-govuk-grey-2 font-mono">Run #{{ audio.id }}</span>
                  </div>

                  <h4 class="font-bold text-sm text-govuk-black mb-2 truncate">
                    {{ activeScript?.title || 'Synthesized Version' }}
                  </h4>
                  
                  <div class="bg-govuk-grey-4 p-2.5 mb-4 text-xs space-y-1 rounded border border-govuk-grey-3/50 font-sans">
                    <div class="flex justify-between"><span class="text-govuk-grey-1">Speed:</span> <span class="font-bold text-govuk-black">{{ audio.settings?.speed || '1.0' }}x</span></div>
                    <div class="flex justify-between"><span class="text-govuk-grey-1">Host Voice:</span> <span class="font-bold text-govuk-black truncate max-w-[120px]">{{ audio.settings?.voice_host || 'bf_alice' }}</span></div>
                    <div class="flex justify-between"><span class="text-govuk-grey-1">Guest Voice:</span> <span class="font-bold text-govuk-black truncate max-w-[120px]">{{ audio.settings?.voice_guest || 'bm_george' }}</span></div>
                    <div class="flex justify-between pt-1 border-t border-govuk-grey-3/30"><span class="text-[9px] text-govuk-grey-2">Created:</span> <span class="text-[9px] text-govuk-grey-2 font-semibold">{{ new Date(audio.created_at).toLocaleString() }}</span></div>
                  </div>
                </div>

                <div class="flex gap-2">
                  <button 
                    @click="playAudioRecord(audio)" 
                    class="flex-1 bg-govuk-blue text-white py-1 px-3 text-xs font-bold flex items-center justify-center gap-1.5 shadow-[0_2px_0_0_#154f83] hover:bg-[#154f83] active:translate-y-0.5 active:shadow-none"
                  >
                    <Play class="h-3.5 w-3.5" /> Play
                  </button>
                  <button 
                    @click="handleDeleteAudio(audio.id)" 
                    class="bg-govuk-red text-white p-1 px-2.5 hover:bg-[#a62612] active:translate-y-0.5 shadow-[0_2px_0_0_#a62612] active:shadow-none"
                    title="Delete variation"
                  >
                    <Trash2 class="h-4.5 w-4.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<style scoped>
:deep(.markdown-content h1) {
  font-size: 1.5rem;
  font-weight: 800;
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
  color: #0b0c0c; /* govuk-black */
  border-bottom: 2px solid #bfc1c3; /* govuk-grey-3 */
  padding-bottom: 0.25rem;
}

:deep(.markdown-content h2) {
  font-size: 1.25rem;
  font-weight: 700;
  margin-top: 1.25rem;
  margin-bottom: 0.5rem;
  color: #0b0c0c;
}

:deep(.markdown-content h3) {
  font-size: 1.1rem;
  font-weight: 700;
  margin-top: 1rem;
  margin-bottom: 0.5rem;
  color: #0b0c0c;
}

:deep(.markdown-content p) {
  margin-top: 0;
  margin-bottom: 0.75rem;
  line-height: 1.6;
  color: #0b0c0c;
}

:deep(.markdown-content ul), :deep(.markdown-content ol) {
  margin-top: 0;
  margin-bottom: 0.75rem;
  padding-left: 1.5rem;
  list-style-position: outside;
}

:deep(.markdown-content ul) {
  list-style-type: disc;
}

:deep(.markdown-content ol) {
  list-style-type: decimal;
}

:deep(.markdown-content li) {
  margin-bottom: 0.25rem;
  line-height: 1.5;
}

:deep(.markdown-content strong) {
  font-weight: 700;
  color: #000;
}

:deep(.markdown-content blockquote) {
  margin: 1rem 0;
  padding-left: 1rem;
  border-left: 4px solid #005ea5; /* govuk-blue */
  color: #505a5f; /* govuk-grey-1 */
  font-style: italic;
}

:deep(.markdown-content code) {
  font-family: monospace;
  background-color: #f3f2f1; /* govuk-grey-4 */
  padding: 0.125rem 0.25rem;
  border-radius: 3px;
  font-size: 0.875rem;
}

:deep(.markdown-content pre) {
  background-color: #f3f2f1;
  padding: 0.75rem;
  overflow-x: auto;
  border-radius: 4px;
  margin-bottom: 0.75rem;
}

:deep(.markdown-content pre code) {
  background-color: transparent;
  padding: 0;
  border-radius: 0;
  font-size: 0.8125rem;
}

:deep(.markdown-content hr) {
  border: 0;
  border-top: 2px solid #bfc1c3;
  margin: 1.5rem 0;
}

:deep(.markdown-content table) {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 1rem;
  font-size: 0.875rem;
}

:deep(.markdown-content th), :deep(.markdown-content td) {
  border: 1px solid #bfc1c3;
  padding: 0.5rem;
  text-align: left;
}

:deep(.markdown-content th) {
  background-color: #f3f2f1;
  font-weight: 700;
}
</style>

