<template>
  <v-container class="pa-0">
    <v-container>
      <BaseCardSectionTitle title="Social Media Cookies">
        Upload and check cookies.txt files used for social video recipe imports.
      </BaseCardSectionTitle>

      <v-alert
        v-if="instagramStatus && !instagramStatus.configured"
        type="warning"
        variant="tonal"
        class="my-4"
      >
        INSTAGRAM_COOKIES_FILE is not configured.
      </v-alert>

      <v-alert
        v-else-if="
          instagramStatus
            && instagramStatus.exists
            && instagramStatus.validNetscape
            && instagramStatus.hasPlatformCookies
        "
        type="success"
        variant="tonal"
        class="my-4"
      >
        Instagram cookies are uploaded and readable.
      </v-alert>

      <v-alert
        v-else-if="instagramStatus"
        type="warning"
        variant="tonal"
        class="my-4"
      >
        {{ instagramStatus.message || "Instagram cookies are not ready." }}
      </v-alert>

      <v-list
        v-if="instagramStatus"
        density="compact"
      >
        <v-list-item
          title="Configured"
          :subtitle="instagramStatus.configured ? 'yes' : 'no'"
        />
        <v-list-item
          title="File uploaded"
          :subtitle="instagramStatus.exists ? 'yes' : 'no'"
        />
        <v-list-item
          title="Writable"
          :subtitle="instagramStatus.writable ? 'yes' : 'no'"
        />
        <v-list-item
          title="Instagram cookies"
          :subtitle="instagramStatus.hasPlatformCookies ? 'found' : 'missing'"
        />
        <v-list-item
          title="Updated"
          :subtitle="instagramStatus.updatedAt ? new Date(instagramStatus.updatedAt).toLocaleString() : '-'"
        />
      </v-list>

      <input
        ref="instagramFileInput"
        class="d-none"
        type="file"
        accept=".txt,text/plain"
        @change="uploadInstagramCookies"
      >

      <v-card-actions class="px-0">
        <BaseButton
          :disabled="!instagramStatus?.configured"
          :loading="loading"
          @click="instagramFileInput?.click()"
        >
          <template #icon>
            {{ $globals.icons.upload }}
          </template>
          Upload cookies.txt
        </BaseButton>
        <BaseButton
          class="ml-2"
          :loading="loading"
          @click="loadStatus"
        >
          <template #icon>
            {{ $globals.icons.refresh }}
          </template>
          Refresh
        </BaseButton>
      </v-card-actions>

      <BaseCardSectionTitle
        title="YouTube Cookies"
        class="mt-8"
      >
        Upload and check the cookies.txt file used for YouTube Shorts recipe imports.
      </BaseCardSectionTitle>

      <v-alert
        v-if="youtubeStatus && !youtubeStatus.configured"
        type="warning"
        variant="tonal"
        class="my-4"
      >
        YOUTUBE_COOKIES_FILE is not configured.
      </v-alert>

      <v-alert
        v-else-if="
          youtubeStatus
            && youtubeStatus.exists
            && youtubeStatus.validNetscape
            && youtubeStatus.hasPlatformCookies
        "
        type="success"
        variant="tonal"
        class="my-4"
      >
        YouTube cookies are uploaded and readable.
      </v-alert>

      <v-alert
        v-else-if="youtubeStatus"
        type="warning"
        variant="tonal"
        class="my-4"
      >
        {{ youtubeStatus.message || "YouTube cookies are not ready." }}
      </v-alert>

      <v-list
        v-if="youtubeStatus"
        density="compact"
      >
        <v-list-item
          title="Configured"
          :subtitle="youtubeStatus.configured ? 'yes' : 'no'"
        />
        <v-list-item
          title="File uploaded"
          :subtitle="youtubeStatus.exists ? 'yes' : 'no'"
        />
        <v-list-item
          title="Writable"
          :subtitle="youtubeStatus.writable ? 'yes' : 'no'"
        />
        <v-list-item
          title="YouTube cookies"
          :subtitle="youtubeStatus.hasPlatformCookies ? 'found' : 'missing'"
        />
        <v-list-item
          title="Updated"
          :subtitle="youtubeStatus.updatedAt ? new Date(youtubeStatus.updatedAt).toLocaleString() : '-'"
        />
      </v-list>

      <input
        ref="youtubeFileInput"
        class="d-none"
        type="file"
        accept=".txt,text/plain"
        @change="uploadYoutubeCookies"
      >

      <v-card-actions class="px-0">
        <BaseButton
          :disabled="!youtubeStatus?.configured"
          :loading="loading"
          @click="youtubeFileInput?.click()"
        >
          <template #icon>
            {{ $globals.icons.upload }}
          </template>
          Upload YouTube cookies.txt
        </BaseButton>
      </v-card-actions>
    </v-container>
  </v-container>
</template>

<script setup lang="ts">
import { useAdminApi } from "~/composables/api";
import { alert } from "~/composables/use-toast";
import type { SocialCookiesStatus } from "~/lib/api/types/admin";

definePageMeta({
  layout: "admin",
});

useSeoMeta({
  title: "Social Media Cookies",
});

const api = useAdminApi();
const loading = ref(false);
const instagramStatus = ref<SocialCookiesStatus | null>(null);
const youtubeStatus = ref<SocialCookiesStatus | null>(null);
const instagramFileInput = ref<HTMLInputElement | null>(null);
const youtubeFileInput = ref<HTMLInputElement | null>(null);

async function loadStatus() {
  loading.value = true;
  const [instagram, youtube] = await Promise.all([
    api.debug.getInstagramCookiesStatus(),
    api.debug.getYoutubeCookiesStatus(),
  ]);
  instagramStatus.value = instagram.data || null;
  youtubeStatus.value = youtube.data || null;
  loading.value = false;
}

async function uploadInstagramCookies(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;

  loading.value = true;
  try {
    const { data } = await api.debug.uploadInstagramCookies(file);
    instagramStatus.value = data || null;
    alert.success("Instagram cookies uploaded");
  }
  catch {
    alert.error("Instagram cookie upload failed");
  }
  loading.value = false;
}

async function uploadYoutubeCookies(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;

  loading.value = true;
  try {
    const { data } = await api.debug.uploadYoutubeCookies(file);
    youtubeStatus.value = data || null;
    alert.success("YouTube cookies uploaded");
  }
  catch {
    alert.error("YouTube cookie upload failed");
  }
  loading.value = false;
}

onMounted(loadStatus);
</script>
