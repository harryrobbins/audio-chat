<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { Folder, FolderPlus, FileText, Calendar, Plus, Loader, ArrowRight } from 'lucide-vue-next'

const router = useRouter()
const API_BASE = 'http://localhost:8000'

interface Project {
  id: number
  name: string
  description: string
  created_at: string
}

const projects = ref<Project[]>([])
const loading = ref(true)
const creating = ref(false)
const errorMsg = ref('')

// Form state
const name = ref('')
const description = ref('')
const showCreateForm = ref(false)

const fetchProjects = async () => {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await axios.get(`${API_BASE}/projects/`)
    projects.value = res.data || []
  } catch (err: any) {
    console.error('Error fetching projects:', err)
    errorMsg.value = 'Failed to load projects. Please ensure the backend is running at ' + API_BASE
  } finally {
    loading.value = false
  }
}

const handleCreateProject = async () => {
  if (!name.value.trim()) return

  creating.value = true
  errorMsg.value = ''
  try {
    const res = await axios.post(`${API_BASE}/projects/`, {
      name: name.value.trim(),
      description: description.value.trim()
    })
    const newProj = res.data
    name.value = ''
    description.value = ''
    showCreateForm.value = false
    // Refresh list
    await fetchProjects()
    // Redirect to detail view
    router.push(`/project/${newProj.id}`)
  } catch (err: any) {
    console.error('Error creating project:', err)
    errorMsg.value = 'Failed to create project. Please try again.'
  } finally {
    creating.value = false
  }
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch (e) {
    return dateStr
  }
}

onMounted(() => {
  fetchProjects()
})
</script>

<template>
  <div class="govuk-grid">
    <div class="mb-8">
      <h1 class="govuk-heading-l flex items-center gap-3">
        <Folder class="h-9 w-9 text-govuk-blue" />
        Podcast Projects Dashboard
      </h1>
      <p class="govuk-body text-govuk-grey-1 max-w-3xl">
        Welcome to the Department's podcast synthesis suite. Here you can organize research materials, run Google ADK multi-agent script refinement cycles, and compile dual-speaker British-voice podcasts powered by the Kokoro-82M TTS engine.
      </p>
    </div>

    <!-- Alert / Error message -->
    <div v-if="errorMsg" class="bg-govuk-red/10 border-l-4 border-govuk-red p-4 mb-6" role="alert">
      <p class="font-bold text-govuk-red">System Alert</p>
      <p class="text-sm text-govuk-black">{{ errorMsg }}</p>
      <button @click="fetchProjects" class="mt-2 text-xs font-bold underline text-govuk-black hover:text-govuk-grey-1">
        Retry connection
      </button>
    </div>

    <!-- Action Bar -->
    <div class="flex justify-between items-center mb-6">
      <h2 class="govuk-heading-m m-0">Active Projects</h2>
      <button 
        @click="showCreateForm = !showCreateForm" 
        class="govuk-button flex items-center gap-2"
        id="btn-toggle-create"
      >
        <Plus v-if="!showCreateForm" class="h-5 w-5" />
        <Folder class="h-5 w-5" v-else />
        {{ showCreateForm ? 'View Projects' : 'Create New Project' }}
      </button>
    </div>

    <!-- Create Project Form Panel -->
    <div v-if="showCreateForm" class="govuk-panel transition-all duration-300" id="create-project-panel">
      <h3 class="govuk-heading-m flex items-center gap-2">
        <FolderPlus class="h-6 w-6 text-govuk-green" />
        Record a New Project Directory
      </h3>
      <form @submit.prevent="handleCreateProject" class="space-y-4 max-w-2xl">
        <div>
          <label for="project-name" class="block text-lg font-bold mb-2">
            Project Title <span class="text-govuk-red">*</span>
          </label>
          <span class="block text-sm text-govuk-grey-2 mb-2">Provide a clear, distinct title for this podcast project.</span>
          <input 
            type="text" 
            id="project-name" 
            v-model="name" 
            required 
            placeholder="e.g., Palestine Historical Records Podcast" 
            class="govuk-input"
          />
        </div>

        <div>
          <label for="project-description" class="block text-lg font-bold mb-2">
            Briefing & Objectives
          </label>
          <span class="block text-sm text-govuk-grey-2 mb-2">Outline the background context and audience targets for this series.</span>
          <textarea 
            id="project-description" 
            v-model="description" 
            rows="4" 
            placeholder="e.g., An educational dialogue summarizing the diplomatic archives, focusing on archival source materials." 
            class="govuk-input"
          ></textarea>
        </div>

        <div class="flex items-center gap-4 pt-2">
          <button 
            type="submit" 
            :disabled="creating || !name.trim()" 
            class="govuk-button flex items-center gap-2"
            id="btn-submit-project"
          >
            <Loader v-if="creating" class="h-5 w-5 animate-spin" />
            <span>Create Project Directory</span>
          </button>
          <button 
            type="button" 
            @click="showCreateForm = false" 
            class="govuk-button-secondary"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>

    <!-- Projects List / Loading State -->
    <div v-else>
      <div v-if="loading" class="flex flex-col items-center justify-center py-12">
        <Loader class="h-10 w-10 text-govuk-blue animate-spin mb-4" />
        <p class="govuk-body text-govuk-grey-2">Retrieving system database files...</p>
      </div>

      <div v-else-if="projects.length === 0" class="border-4 border-dashed border-govuk-grey-3 p-12 text-center">
        <FolderPlus class="h-16 w-16 text-govuk-grey-2 mx-auto mb-4" />
        <p class="govuk-heading-m text-govuk-grey-1 mb-2">No Active Projects Found</p>
        <p class="govuk-body text-govuk-grey-2 mb-6">Create your first project directory to begin uploading documentation and generating transcripts.</p>
        <button @click="showCreateForm = true" class="govuk-button">
          Create New Project
        </button>
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div 
          v-for="project in projects" 
          :key="project.id" 
          class="border-4 border-govuk-grey-3 p-6 bg-govuk-white hover:border-govuk-blue hover:shadow-md transition-all flex flex-col justify-between"
        >
          <div>
            <div class="flex justify-between items-start mb-3">
              <span class="bg-govuk-grey-4 text-govuk-grey-1 px-2 py-0.5 text-xs font-bold tracking-wider">
                REF: #00{{ project.id }}
              </span>
              <span class="text-xs text-govuk-grey-2 flex items-center gap-1">
                <Calendar class="h-3.5 w-3.5" />
                {{ formatDate(project.created_at) }}
              </span>
            </div>
            
            <h3 class="govuk-heading-m text-govuk-black hover:text-govuk-blue mb-2">
              <router-link :to="'/project/' + project.id">{{ project.name }}</router-link>
            </h3>
            
            <p class="govuk-body text-govuk-grey-1 text-sm line-clamp-3 mb-6">
              {{ project.description || 'No description provided.' }}
            </p>
          </div>

          <div class="border-t border-govuk-grey-4 pt-4 flex justify-between items-center">
            <span class="text-xs text-govuk-grey-2 flex items-center gap-1">
              <FileText class="h-3.5 w-3.5" />
              Source Material Integrated
            </span>
            <router-link 
              :to="'/project/' + project.id" 
              class="govuk-button flex items-center gap-1.5 py-1 px-3 text-sm font-bold"
            >
              <span>Manage</span>
              <ArrowRight class="h-4 w-4" />
            </router-link>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
