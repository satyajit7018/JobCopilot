/**
 * TypeScript definitions for JobCopilotClient v1
 */

export interface ApiResponse<T = any> {
  status: string;
  data?: T;
  [key: string]: any;
}

export declare class JobCopilotClient {
  baseUrl: string;
  token: string | null;

  constructor(baseUrl?: string, token?: string | null);
  setToken(token: string): void;
  request<T = any>(endpoint: string, method?: string, body?: any, customHeaders?: Record<string, string>): Promise<T>;

  auth: {
    login(email: string, password: string): Promise<ApiResponse>;
    register(userData: Record<string, any>): Promise<ApiResponse>;
    refresh(refreshToken: string): Promise<ApiResponse>;
    me(): Promise<ApiResponse>;
    logout(): Promise<ApiResponse>;
  };

  jobs: {
    list(status?: string | null): Promise<ApiResponse>;
    get(jobId: string): Promise<ApiResponse>;
    update(jobId: string, data: Record<string, any>): Promise<ApiResponse>;
    apply(jobId: string, dryRun?: boolean): Promise<ApiResponse>;
  };

  analytics: {
    getFunnel(): Promise<ApiResponse>;
    getEvents(): Promise<ApiResponse>;
    trackEvent(eventData: Record<string, any>): Promise<ApiResponse>;
    getCohorts(interval?: string): Promise<ApiResponse>;
    getConversions(): Promise<ApiResponse>;
    getExperiments(): Promise<ApiResponse>;
    createExperiment(expData: Record<string, any>): Promise<ApiResponse>;
    evaluateExperiment(expId: string): Promise<ApiResponse>;
  };
}
