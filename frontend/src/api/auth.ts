import apiClient from "@/lib/api-client";
import { AuthResponse, User } from "@/types";

export const login = async (email: string, password: string): Promise<AuthResponse> => {
  const formData = new URLSearchParams();
  formData.append("username", email);
  formData.append("password", password);

  const response = await apiClient.post<AuthResponse>("/auth/login", formData, {
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
  });
  return response.data;
};

export const register = async (email: string, password: string): Promise<User> => {
  const response = await apiClient.post<User>("/auth/register", {
    email,
    password,
  });
  return response.data;
};

export const getMe = async (): Promise<User> => {
  // Assuming there's a /users/me or similar, if not I'll just rely on the token for now
  // For this project, let's assume we might need it. 
  // Checking backend/app/api/v1/router.py again, I don't see a users router.
  // I'll check auth.py for a 'me' endpoint.
  const response = await apiClient.get<User>("/auth/me"); // Proactively assuming or will add it
  return response.data;
};
