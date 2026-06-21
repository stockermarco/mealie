import { BaseAPI } from "../base/base-clients";
import type { DebugResponse, SocialCookiesStatus } from "~/lib/api/types/admin";

const prefix = "/api";

const routes = {
  openai: providerId => `${prefix}/admin/debug/openai/${providerId}`,
  instagramCookies: `${prefix}/admin/debug/instagram-cookies`,
  youtubeCookies: `${prefix}/admin/debug/youtube-cookies`,
};

export class AdminDebugAPI extends BaseAPI {
  async getInstagramCookiesStatus() {
    return await this.requests.get<SocialCookiesStatus>(routes.instagramCookies);
  }

  async uploadInstagramCookies(fileObject: Blob | File) {
    const formData = new FormData();
    formData.append("cookies", fileObject);

    return await this.requests.post<SocialCookiesStatus>(routes.instagramCookies, formData);
  }

  async getYoutubeCookiesStatus() {
    return await this.requests.get<SocialCookiesStatus>(routes.youtubeCookies);
  }

  async uploadYoutubeCookies(fileObject: Blob | File) {
    const formData = new FormData();
    formData.append("cookies", fileObject);

    return await this.requests.post<SocialCookiesStatus>(routes.youtubeCookies, formData);
  }

  async debugOpenAI(providerId: string, fileObject: Blob | File | undefined = undefined, fileName = "") {
    let formData: FormData | null = null;
    if (fileObject) {
      formData = new FormData();
      formData.append("image", fileObject);
      formData.append("extension", fileName.split(".").pop() ?? "");
    }

    return await this.requests.post<DebugResponse>(routes.openai(providerId), formData);
  }
}
