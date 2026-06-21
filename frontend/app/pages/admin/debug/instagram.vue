<template>
  <v-container class="pa-0">
    <v-container>
      <BaseCardSectionTitle title="Instagram Cookies">
        Upload and check the cookies.txt file used for Instagram recipe imports.
      </BaseCardSectionTitle>

      <v-alert
        v-if="status && !status.configured"
        type="warning"
        variant="tonal"
        class="my-4"
      >
        INSTAGRAM_COOKIES_FILE is not configured.
      </v-alert>

      <v-alert
        v-else-if="status && status.exists && status.validNetscape && status.hasInstagramCookies"
        type="success"
        variant="tonal"
        class="my-4"
      >
        Instagram cookies are uploaded and readable.
      </v-alert>

      <v-alert
        v-else-if="status"
        type="warning"
        variant="tonal"
        class="my-4"
      >
        {{ status.message || "Instagram cookies are not ready." }}
      </v-alert>

      <v-list
        v-if="status"
        density="compact"
      >
        <v-list-item
          title="Configured"
          :subtitle="status.configured ? 'yes' : 'no'"
        />
        <v-list-item
          title="File uploaded"
          :subtitle="status.exists ? 'yes' : 'no'"
        />
        <v-list-item
          title="Writable"
          :subtitle="status.writable ? 'yes' : 'no'"
        />
        <v-list-item
          title="Instagram cookies"
          :subtitle="status.hasInstagramCookies ? 'found' : 'missing'"
        />
        <v-list-item
          title="Updated"
          :subtitle="status.updatedAt ? new Date(status.updatedAt).toLocaleString() : '-'"
        />
      </v-list>

      <input
        ref="fileInput"
        class="d-none"
        type="file"
        accept=".txt,text/plain"
        @change="uploadCookies"
      >

      <v-card-actions class="px-0">
        <BaseButton
          :disabled="!status?.configured"
          :loading="loading"
          @click="fileInput?.click()"
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
    </v-container>
  </v-container>
</template>

<script setup lang="ts">
import { useAdminApi } from "~/composables/api";
import { alert } from "~/composables/use-toast";
import type { InstagramCookiesStatus } from "~/lib/api/types/admin";

definePageMeta({
  layout: "admin",
});

useSeoMeta({
  title: "Instagram Cookies",
});

const api = useAdminApi();
const loading = ref(false);
const status = ref<InstagramCookiesStatus | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);

async function loadStatus() {
  loading.value = true;
  const { data } = await api.debug.getInstagramCookiesStatus();
  status.value = data || null;
  loading.value = false;
}

async function uploadCookies(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;

  loading.value = true;
  try {
    const { data } = await api.debug.uploadInstagramCookies(file);
    status.value = data || null;
    alert.success("Instagram cookies uploaded");
  }
  catch {
    alert.error("Instagram cookie upload failed");
  }
  loading.value = false;
}

onMounted(loadStatus);
</script>
