import { AxiosRequestConfig } from 'axios';
import { ApiResponse, GET, POST } from '../index';

// Voice process result for a single file
export interface VoiceProcessResultFile {
  fileUid: string;
  fileName: string;
  text: string;
  processingTime: number;
  success: boolean;
  error?: string;
  duration?: number; // Duration in seconds
  outputFile?: string; // Filename of the output transcript
  autoRegisteredSpeakers?: number; // Count of auto-registered speakers
}

// Voice process result for all files
export interface VoiceProcessResult {
  fileCount: number;
  totalDuration: number; // Total duration in seconds
  processedFiles: number;
  failedFiles: number;
  files: VoiceProcessResultFile[];
  autoRegisteredSpeakers?: number; // Total count of auto-registered speakers
  autoRegisteredSpeakerIds?: string[]; // IDs of auto-registered speakers
}

// Voice process parameters
export interface ProcessVoiceToTextParams {
  // Voice processing options
  language?: string; // Language code (e.g., 'zh-CN', 'en-US')
  model?: string; // Voice recognition model to use
  enablePunctuation?: boolean; // Whether to include punctuation
  speakerDiarization?: boolean; // Whether to identify different speakers

  // New parameters
  auto_register?: boolean; // Whether to register unknown voices automatically
  threshold?: number; // Voice matching threshold (0-1)
  hotword?: string; // Hot words separated by spaces

  // File data, using FormData for direct upload
  fileData: FormData;
}

/**
 * Process voice files to text
 * @param params Processing parameters and configuration
 * @returns Processing result Promise
 */
export const postProcessVoiceToText = ({
  language = 'zh-CN',
  model = 'default',
  enablePunctuation = true,
  speakerDiarization = true,
  auto_register = true,
  threshold = 0.5,
  hotword = '',
  fileData,
  config,
}: ProcessVoiceToTextParams & {
  config?: AxiosRequestConfig;
}): Promise<ApiResponse<VoiceProcessResult, any>> => {
  const baseUrl = '/api/v1/expand/voiceprocess/voice2text';

  // Add non-sensitive parameters to URL query
  const urlParams: Record<string, any> = {
    language,
    model,
    enablePunctuation: enablePunctuation ? 'true' : 'false',
    speakerDiarization: speakerDiarization ? 'true' : 'false',
    auto_register,
    threshold,
    hotword,
  };

  // Build URL with query parameters
  const queryString = Object.keys(urlParams)
    .map(key => `${encodeURIComponent(key)}=${encodeURIComponent(urlParams[key])}`)
    .join('&');

  const url = queryString ? `${baseUrl}?${queryString}` : baseUrl;

  return POST<FormData, VoiceProcessResult>(url, fileData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    ...config,
  });
};

// Voice profile related types and APIs
export interface VoiceSample {
  id: string;
  name: string;
  duration: string;
  uploadDate: string;
  url?: string;
}

export interface VoiceProfile {
  id: string; // Changed from number to string to match backend
  name: string;
  type?: string; // 'named' or 'unnamed'
  samples: VoiceSample[];
  sampleCount?: number;
}

export interface VoiceProfileResponse {
  profiles: VoiceProfile[];
}

// Get all voice profiles
export const getVoiceProfiles = (
  includeUnnamed: boolean = true,
  config?: AxiosRequestConfig,
): Promise<ApiResponse<VoiceProfileResponse, any>> => {
  return GET<VoiceProfileResponse>(`/api/v1/expand/voiceprofile/list?include_unnamed=${includeUnnamed}`, config);
};

// Create a new voice profile
export const createVoiceProfile = (
  name: string,
  file?: File, // Optional audio file
  config?: AxiosRequestConfig,
): Promise<ApiResponse<VoiceProfile, any>> => {
  const formData = new FormData();
  formData.append('name', name);

  if (file) {
    formData.append('file', file);
  }

  return POST<FormData, VoiceProfile>('/api/v1/expand/voiceprofile/create', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    ...config,
  });
};

// Update a voice profile name
export const updateVoiceProfile = (
  id: string, // Changed from number to string
  name: string,
  config?: AxiosRequestConfig,
): Promise<ApiResponse<VoiceProfile, any>> => {
  const formData = new FormData();
  formData.append('id', id);
  formData.append('name', name);

  return POST<FormData, VoiceProfile>('/api/v1/expand/voiceprofile/update', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    ...config,
  });
};

// Delete a voice profile
export const deleteVoiceProfile = (
  id: string, // Changed from number to string
  config?: AxiosRequestConfig,
): Promise<ApiResponse<{ success: boolean; message?: string }, any>> => {
  const formData = new FormData();
  formData.append('id', id);

  return POST<FormData, { success: boolean; message?: string }>('/api/v1/expand/voiceprofile/delete', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    ...config,
  });
};

// Add a voice sample to a profile
export const addVoiceSample = (
  profileId: string, // Changed from number to string
  fileData: FormData,
  config?: AxiosRequestConfig,
): Promise<ApiResponse<VoiceSample, any>> => {
  fileData.append('profileId', profileId);

  return POST<FormData, VoiceSample>('/api/v1/expand/voiceprofile/addsample', fileData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    ...config,
  });
};

// Delete a voice sample
export const deleteVoiceSample = (
  sampleId: string,
  config?: AxiosRequestConfig,
): Promise<ApiResponse<{ success: boolean; message?: string }, any>> => {
  const formData = new FormData();
  formData.append('sampleId', sampleId);

  return POST<FormData, { success: boolean; message?: string }>('/api/v1/expand/voiceprofile/deletesample', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    ...config,
  });
};

// Get a specific voice sample audio file
export const getVoiceSample = (sampleId: string): string => {
  return `/api/v1/expand/voiceprofile/sample/${sampleId}`;
};

// Clear all voice profiles
export const clearVoiceProfiles = (
  config?: AxiosRequestConfig,
): Promise<ApiResponse<{ success: boolean; message?: string }, any>> => {
  return POST<null, { success: boolean; message?: string }>('/api/v1/expand/voiceprofile/clear', null, config);
};

// Batch register voice profiles from a directory
export const batchRegisterVoiceProfiles = (
  directory: string,
  config?: AxiosRequestConfig,
): Promise<ApiResponse<{ success: boolean; message?: string; registeredVoices?: Record<string, string> }, any>> => {
  const formData = new FormData();
  formData.append('directory', directory);

  return POST<FormData, { success: boolean; message?: string; registeredVoices?: Record<string, string> }>(
    '/api/v1/expand/voiceprofile/batchregister',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      ...config,
    },
  );
};
