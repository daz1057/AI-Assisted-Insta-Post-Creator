import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import json
import os
import csv
import boto3
import time
import openai
import logging

# Set up basic configuration for logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class App:
    def __init__(self, root):
        self.root = root
        logging.info("Application initialized")
        self.root.title("Customer Information and Prompts Management")

        self.tabs = ttk.Notebook(root)
        self.config_tab = ttk.Frame(self.tabs)
        self.generate_tab = ttk.Frame(self.tabs)
        self.curate_tab = ttk.Frame(self.tabs)

        self.tabs.add(self.config_tab, text="Config")
        self.tabs.add(self.generate_tab, text="Generate")
        self.tabs.add(self.curate_tab, text="Curate")
        self.tabs.pack(expand=1, fill="both")

        self.customer_info_list = []
        self.prompts_list = []
        self.published_posts = []
        self.unpublished_posts = []
        self.customer_detail_vars = {}
        self.generated_response = None
        self.current_unpublished_index = 0
        self.current_published_index = 0
        self.s3_client = boto3.client('s3')
        self.unpublished_tags_dropdown = None
        self.published_tags_dropdown = None

        self.create_config_tab()
        self.create_generate_tab()
        self.create_curate_tab()

        self.load_customer_info_from_file()
        self.load_prompts_from_file()
        self.load_prompt_titles()  # Load prompt titles here

        # Create customer detail vars and load the previously selected customer information
        self.update_customer_detail_vars()
        self.load_selected_customer_info()


    def save_tag(self):
        tag_name = self.tag_entry.get().strip()
        if not tag_name:
            messagebox.showwarning("Warning", "Please enter a tag name.")
            return

        tags = self.load_from_file("tags.json", default=[])
        if not any(tag['name'] == tag_name for tag in tags):
            tags.append({"name": tag_name})
            self.save_to_file(tags, "tags.json")
            self.load_tags()
            self.load_tags_dropdown(self.unpublished_tags_dropdown)
            self.load_tags_dropdown(self.published_tags_dropdown)
            messagebox.showinfo("Success", "Tag saved successfully.")
        else:
            messagebox.showwarning("Warning", "Tag already exists.")

    def delete_tag(self):
        selected_tag_index = self.tags_list.curselection()
        if not selected_tag_index:
            messagebox.showwarning("Warning", "Please select a tag to delete.")
            return

        tags = self.load_from_file("tags.json", default=[])
        tag_to_delete = self.tags_list.get(selected_tag_index)

        tags = [tag for tag in tags if tag['name'] != tag_to_delete]
        self.save_to_file(tags, "tags.json")
        self.load_tags()
        self.load_tags_dropdown(self.unpublished_tags_dropdown)
        self.load_tags_dropdown(self.published_tags_dropdown)
        messagebox.showinfo("Success", "Tag deleted successfully.")

    def load_tags(self):
        tags = self.load_from_file("tags.json", default=[])
        logging.info(f"Loaded tags: {tags}")  # Use logging instead of print
        self.tags_list.delete(0, tk.END)
        for tag in tags:
            if isinstance(tag, dict) and 'name' in tag:
                self.tags_list.insert(tk.END, tag['name'])
            else:
                logging.warning(f"Unexpected tag format: {tag}")
                messagebox.showwarning("Warning", f"Unexpected tag format: {tag}")

    def create_config_tab(self):
        self.config_tabs = ttk.Notebook(self.config_tab)
        self.customer_info_tab = ttk.Frame(self.config_tabs)
        self.prompts_tab = ttk.Frame(self.config_tabs)
        self.credentials_tab = ttk.Frame(self.config_tabs)
        self.chatgpt_tab = ttk.Frame(self.config_tabs)
        self.tags_tab = ttk.Frame(self.config_tabs)  # New Tags Tab

        self.config_tabs.add(self.customer_info_tab, text="Customer Information")
        self.config_tabs.add(self.prompts_tab, text="Prompts")
        self.config_tabs.add(self.credentials_tab, text="AWS Credentials")
        self.config_tabs.add(self.chatgpt_tab, text="ChatGPT")
        self.config_tabs.add(self.tags_tab, text="Tags")  # Add Tags Tab
        self.config_tabs.pack(expand=1, fill="both")

        self.create_customer_info_tab()
        self.create_prompts_tab()
        self.create_credentials_tab()
        self.create_chatgpt_tab()
        self.create_tags_tab()  # Create Tags Tab

        self.logs_tab = ttk.Frame(self.config_tabs)
        self.config_tabs.add(self.logs_tab, text="Logs")
        self.create_logs_tab()

    def load_prompts_from_file(self):
        self.prompts_list = self.load_from_file("prompts.json")

    def load_prompt_titles(self):
        self.prompt_titles_listbox.delete(0, tk.END)
        for prompt in self.prompts_list:
            self.prompt_titles_listbox.insert(tk.END, prompt['name'])

    def create_generate_tab(self):
        self.generate_label = tk.Label(self.generate_tab, text="Generate Posts")
        self.generate_label.pack(pady=10)

        # Frame to hold the Listbox and Scrollbar
        self.prompt_list_frame = tk.Frame(self.generate_tab)
        self.prompt_list_frame.pack(pady=5, fill=tk.BOTH, expand=True)

        # Listbox for prompt titles
        self.prompt_titles_listbox = tk.Listbox(self.prompt_list_frame)
        self.prompt_titles_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.prompt_titles_listbox.bind("<<ListboxSelect>>", self.display_prompt_description)

        # Scrollbar for the Listbox
        self.prompt_list_scrollbar = tk.Scrollbar(self.prompt_list_frame, orient=tk.VERTICAL)
        self.prompt_list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Link the Listbox and Scrollbar
        self.prompt_titles_listbox.config(yscrollcommand=self.prompt_list_scrollbar.set)
        self.prompt_list_scrollbar.config(command=self.prompt_titles_listbox.yview)

        self.prompt_description_label = tk.Label(self.generate_tab, text="Prompt Description")
        self.prompt_description_label.pack(pady=10)
        self.prompt_description_text = tk.Text(self.generate_tab, height=5, state='disabled')
        self.prompt_description_text.pack(pady=5)

        self.num_posts_label = tk.Label(self.generate_tab, text="Number of Posts:")
        self.num_posts_label.pack(pady=5)
        self.num_posts_entry = tk.Entry(self.generate_tab)
        self.num_posts_entry.pack(pady=5)

        self.generate_posts_button = tk.Button(self.generate_tab, text="Generate Posts", command=self.generate_posts)
        self.generate_posts_button.pack(pady=10)

        self.submit_prompt_button = tk.Button(self.generate_tab, text="Submit to ChatGPT",
                                              command=self.submit_to_chatgpt)
        self.submit_prompt_button.pack(pady=10)

        self.refresh_prompts_button = tk.Button(self.generate_tab, text="Refresh Prompts",
                                                command=self.refresh_prompts_list)
        self.refresh_prompts_button.pack(pady=10)

        logging.info("Generate tab created successfully.")

    def refresh_prompts_list(self):
            self.prompts_list = self.load_from_file("prompts.json")
            self.load_prompt_titles()
            messagebox.showinfo("Success", "Prompts list refreshed.")

    def display_prompt_description(self, event):
        selected_index = self.prompt_titles_listbox.curselection()
        if not selected_index:
            return

        selected_index = int(self.prompt_titles_listbox.curselection()[0])
        selected_prompt = self.prompts_list[selected_index]
        self.prompt_description_text.config(state='normal')
        self.prompt_description_text.delete("1.0", tk.END)
        self.prompt_description_text.insert(tk.END, selected_prompt['details'])
        self.prompt_description_text.config(state='disabled')
    def create_curate_tab(self):
        self.curate_tabs = ttk.Notebook(self.curate_tab)
        self.unpublished_tab = ttk.Frame(self.curate_tabs)
        self.published_tab = ttk.Frame(self.curate_tabs)

        self.curate_tabs.add(self.unpublished_tab, text="Unpublished")
        self.curate_tabs.add(self.published_tab, text="Published")
        self.curate_tabs.pack(expand=1, fill="both")

        self.create_unpublished_tab()
        self.create_published_tab()

        # Load the prompt settings when the Curate tab is created
        self.load_prompt_settings()

    def create_logs_tab(self):
        self.logs_text = tk.Text(self.logs_tab, wrap="word")
        self.logs_text.pack(expand=True, fill="both")
        self.load_logs_button = tk.Button(self.logs_tab, text="Load Logs", command=self.load_and_display_logs)
        self.load_logs_button.pack(pady=10)

    def create_tags_tab(self):
        self.tags_list = tk.Listbox(self.tags_tab)
        self.tags_list.pack(pady=5, fill="both", expand=True)

        self.tag_entry = tk.Entry(self.tags_tab)
        self.tag_entry.pack(pady=5)

        self.tags_buttons_frame = tk.Frame(self.tags_tab)
        self.tags_buttons_frame.pack(pady=5)

        self.save_tag_button = tk.Button(self.tags_buttons_frame, text="Save Tag", command=self.save_tag)
        self.save_tag_button.grid(row=0, column=0, padx=5)

        self.delete_tag_button = tk.Button(self.tags_buttons_frame, text="Delete Tag", command=self.delete_tag)
        self.delete_tag_button.grid(row=0, column=1, padx=5)

        self.load_tags()

    def create_customer_info_tab(self):
        self.customer_info_name = tk.Entry(self.customer_info_tab)
        self.customer_info_name.pack(pady=5)
        self.customer_info_name.insert(0, "Customer Information Name")

        self.customer_info_details = tk.Text(self.customer_info_tab, height=10)
        self.customer_info_details.pack(pady=5)

        self.customer_search_results = ttk.Combobox(self.customer_info_tab)
        self.customer_search_results.pack(pady=5)

        self.customer_crud_buttons = tk.Frame(self.customer_info_tab)
        self.customer_crud_buttons.pack(pady=5)

        self.create_customer_crud_buttons(self.customer_crud_buttons)

    def create_customer_crud_buttons(self, frame):
        self.search_button = tk.Button(frame, text="Search", command=self.search_customer_info)
        self.search_button.grid(row=0, column=0, padx=5)
        self.create_button = tk.Button(frame, text="Create", command=self.create_customer_info)
        self.create_button.grid(row=0, column=1, padx=5)
        self.read_button = tk.Button(frame, text="Read", command=self.read_customer_info)
        self.read_button.grid(row=0, column=2, padx=5)
        self.update_button = tk.Button(frame, text="Update", command=self.update_customer_info)
        self.update_button.grid(row=0, column=3, padx=5)
        self.delete_button = tk.Button(frame, text="Delete", command=self.delete_customer_info)
        self.delete_button.grid(row=0, column=4, padx=5)

    def create_prompts_tab(self):
        self.prompt_name = tk.Entry(self.prompts_tab)
        self.prompt_name.pack(pady=5)
        self.prompt_name.insert(0, "Prompt Name")

        self.prompt_details = tk.Text(self.prompts_tab, height=10)
        self.prompt_details.pack(pady=5)

        self.prompt_search_results = ttk.Combobox(self.prompts_tab)
        self.prompt_search_results.pack(pady=5)

        self.customer_details_frame = tk.Frame(self.prompts_tab)  # Move this frame to prompts tab
        self.customer_details_frame.pack(pady=5, fill="both", expand=True)

        self.prompt_crud_buttons = tk.Frame(self.prompts_tab)
        self.prompt_crud_buttons.pack(pady=5)

        self.create_prompt_crud_buttons(self.prompt_crud_buttons)

        self.save_settings_button = tk.Button(self.prompts_tab, text="Save Settings", command=self.save_prompt_settings)
        self.save_settings_button.pack(pady=10)

        # Add the Clear all button
        self.clear_all_button = tk.Button(self.prompts_tab, text="Clear all", command=self.clear_all_prompts)
        self.clear_all_button.pack(pady=10)

    def create_prompt_crud_buttons(self, frame):
        self.prompt_search_button = tk.Button(frame, text="Search", command=self.search_prompt_info)
        self.prompt_search_button.grid(row=0, column=0, padx=5)
        self.prompt_create_button = tk.Button(frame, text="Create", command=self.create_prompt_info)
        self.prompt_create_button.grid(row=0, column=1, padx=5)
        self.prompt_read_button = tk.Button(frame, text="Read", command=self.read_prompt_info)
        self.prompt_read_button.grid(row=0, column=2, padx=5)
        self.prompt_update_button = tk.Button(frame, text="Update", command=self.update_prompt_info)
        self.prompt_update_button.grid(row=0, column=3, padx=5)
        self.prompt_delete_button = tk.Button(frame, text="Delete", command=self.delete_prompt_info)
        self.prompt_delete_button.grid(row=0, column=4, padx=5)

    def clear_all_prompts(self):
        self.prompt_name.delete(0, tk.END)
        self.prompt_details.delete("1.0", tk.END)
        self.prompt_search_results.set("")
        for child in self.customer_details_frame.winfo_children():
            if isinstance(child, tk.Checkbutton):
                child.deselect()

    def create_credentials_tab(self):
        self.aws_access_key_label = tk.Label(self.credentials_tab, text="AWS Access Key ID")
        self.aws_access_key_label.pack(pady=5)
        self.aws_access_key_entry = tk.Entry(self.credentials_tab)
        self.aws_access_key_entry.pack(pady=5)

        self.aws_secret_key_label = tk.Label(self.credentials_tab, text="AWS Secret Access Key")
        self.aws_secret_key_label.pack(pady=5)
        self.aws_secret_key_entry = tk.Entry(self.credentials_tab, show="*")
        self.aws_secret_key_entry.pack(pady=5)

        self.aws_region_label = tk.Label(self.credentials_tab, text="AWS Region")
        self.aws_region_label.pack(pady=5)
        self.aws_region_entry = tk.Entry(self.credentials_tab)
        self.aws_region_entry.pack(pady=5)

        self.save_credentials_button = tk.Button(self.credentials_tab, text="Save Credentials",
                                                 command=self.save_aws_credentials)
        self.save_credentials_button.pack(pady=10)

        self.load_aws_credentials()

    def create_chatgpt_tab(self):
        self.chatgpt_key_label = tk.Label(self.chatgpt_tab, text="ChatGPT API Key")
        self.chatgpt_key_label.pack(pady=5)
        self.chatgpt_key_entry = tk.Entry(self.chatgpt_tab, show="*")
        self.chatgpt_key_entry.pack(pady=5)

        self.save_chatgpt_key_button = tk.Button(self.chatgpt_tab, text="Save ChatGPT API Key",
                                                 command=self.save_chatgpt_key)
        self.save_chatgpt_key_button.pack(pady=10)

        self.delete_chatgpt_key_button = tk.Button(self.chatgpt_tab, text="Delete ChatGPT API Key",
                                                   command=self.delete_chatgpt_key)
        self.delete_chatgpt_key_button.pack(pady=10)

        self.load_chatgpt_key()

    def create_unpublished_tab(self):
        self.unpublished_posts = self.load_from_file("unpublished_posts.json")

        self.unpublished_title = tk.Entry(self.unpublished_tab)
        self.unpublished_title.pack(pady=5)
        self.unpublished_title.insert(0, "Post Title")

        self.unpublished_description = tk.Text(self.unpublished_tab, height=5)
        self.unpublished_description.pack(pady=5)

        self.unpublished_type = tk.Entry(self.unpublished_tab)
        self.unpublished_type.pack(pady=5)
        self.unpublished_type.insert(0, "Graphic Type")

        self.unpublished_caption = tk.Text(self.unpublished_tab, height=3)
        self.unpublished_caption.pack(pady=5)

        self.s3_bucket_url = tk.Entry(self.unpublished_tab)
        self.s3_bucket_url.pack(pady=5)
        self.s3_bucket_url.insert(0, "S3 Bucket URL")

        self.s3_folder_path = tk.Entry(self.unpublished_tab)
        self.s3_folder_path.pack(pady=5)
        self.s3_folder_path.insert(0, "S3 Folder Path")

        self.s3_file_name = tk.Entry(self.unpublished_tab, state='disabled')
        self.s3_file_name.pack(pady=5)
        self.s3_file_name.insert(0, "S3 File Name")

        self.tag_label = tk.Label(self.unpublished_tab, text="Tags")
        self.tag_label.pack(pady=5)
        self.unpublished_tags_dropdown = ttk.Combobox(self.unpublished_tab)
        self.unpublished_tags_dropdown.pack(pady=5)
        self.load_tags_dropdown(self.unpublished_tags_dropdown)

        self.ready_to_publish_var = tk.BooleanVar()
        self.ready_to_publish_checkbox = tk.Checkbutton(self.unpublished_tab, text="Ready to publish",
                                                        variable=self.ready_to_publish_var)
        self.ready_to_publish_checkbox.pack(pady=5)

        self.buttons_frame = tk.Frame(self.unpublished_tab)
        self.buttons_frame.pack(pady=5)

        self.upload_media_button = tk.Button(self.buttons_frame, text="Upload Media", command=self.upload_media)
        self.upload_media_button.grid(row=0, column=0, padx=5)

        self.validate_url_button = tk.Button(self.buttons_frame, text="Validate URL", command=self.validate_url)
        self.validate_url_button.grid(row=0, column=1, padx=5)

        self.unpublished_save_button = tk.Button(self.buttons_frame, text="Save", command=self.save_unpublished_post)
        self.unpublished_save_button.grid(row=0, column=2, padx=5)

        self.unpublished_delete_button = tk.Button(self.buttons_frame, text="Delete",
                                                   command=self.delete_unpublished_post)
        self.unpublished_delete_button.grid(row=0, column=3, padx=5)

        self.unpublished_next_button = tk.Button(self.buttons_frame, text="Next", command=self.next_unpublished_post)
        self.unpublished_next_button.grid(row=0, column=4, padx=5)

        self.unpublished_last_button = tk.Button(self.buttons_frame, text="Last", command=self.last_unpublished_post)
        self.unpublished_last_button.grid(row=0, column=5, padx=5)

        self.unpublished_refresh_button = tk.Button(self.buttons_frame, text="Refresh",
                                                    command=self.refresh_unpublished_posts)
        self.unpublished_refresh_button.grid(row=0, column=6, padx=5)

        self.unpublished_export_button = tk.Button(self.buttons_frame, text="Export", command=self.export_to_csv)
        self.unpublished_export_button.grid(row=0, column=7, padx=5)

        if self.unpublished_posts:
            self.display_unpublished_post(self.unpublished_posts[0])

    def create_published_tab(self):
        self.published_posts = self.load_from_file("published_posts.json")

        self.published_title = tk.Entry(self.published_tab, state='disabled')
        self.published_title.pack(pady=5)

        self.published_description = tk.Text(self.published_tab, height=5, state='disabled')
        self.published_description.pack(pady=5)

        self.published_type = tk.Entry(self.published_tab, state='disabled')
        self.published_type.pack(pady=5)

        self.published_caption = tk.Text(self.published_tab, height=3, state='disabled')
        self.published_caption.pack(pady=5)

        self.tag_label = tk.Label(self.published_tab, text="Tags")
        self.tag_label.pack(pady=5)
        self.published_tags_dropdown = ttk.Combobox(self.published_tab)
        self.published_tags_dropdown.pack(pady=5)
        self.load_tags_dropdown(self.published_tags_dropdown)

        self.buttons_frame = tk.Frame(self.published_tab)
        self.buttons_frame.pack(pady=5)

        self.published_save_button = tk.Button(self.buttons_frame, text="Save", state='disabled')
        self.published_save_button.grid(row=0, column=0, padx=5)

        self.published_delete_button = tk.Button(self.buttons_frame, text="Delete", command=self.delete_published_post)
        self.published_delete_button.grid(row=0, column=1, padx=5)

        self.published_next_button = tk.Button(self.buttons_frame, text="Next", command=self.next_published_post)
        self.published_next_button.grid(row=0, column=2, padx=5)

        self.published_last_button = tk.Button(self.buttons_frame, text="Last", command=self.last_published_post)
        self.published_last_button.grid(row=0, column=3, padx=5)

        self.published_refresh_button = tk.Button(self.buttons_frame, text="Refresh",
                                                  command=self.refresh_published_posts)
        self.published_refresh_button.grid(row=0, column=4, padx=5)

        if self.published_posts:
            self.display_published_post(self.published_posts[0])

    def save_generated_posts_to_json(self, generated_posts):
        self.save_to_file(generated_posts, "generated_posts.json")

    def show_loading(self, message):
        self.loading_label = tk.Label(self.root, text=message)
        self.loading_label.pack()

    def hide_loading(self):
        if hasattr(self, 'loading_label'):
            self.loading_label.destroy()



    def generate_posts(self):
        selected_index = self.prompt_titles_listbox.curselection()
        if not selected_index:
            messagebox.showwarning("Warning", "Please select a prompt to generate posts.")
            return

        num_posts = self.num_posts_entry.get().strip()
        if not num_posts.isdigit() or int(num_posts) <= 0:
            messagebox.showwarning("Warning", "Please enter a valid number of posts.")
            return

        prompt = self.prompts_list[selected_index[0]]
        num_posts = int(num_posts)

        generated_posts = []
        for i in range(num_posts):
            generated_posts.append({
                "PostTitle": f"Generated Post {i + 1}",
                "GraphicDescription": f"Generated Graphic Description {i + 1}",
                "GraphicType": "Type Example",
                "Caption": f"Generated Caption {i + 1}"
            })

        self.save_generated_posts_to_json(generated_posts)
        messagebox.showinfo("Success", f"{num_posts} posts generated and saved to 'generated_posts.json'.")

    def submit_to_chatgpt(self):
        selected_index = self.prompt_titles_listbox.curselection()
        if not selected_index:
            messagebox.showwarning("Warning", "Please select a prompt to send to ChatGPT.")
            return

        selected_prompt = self.prompts_list[selected_index[0]]['details']
        selected_prompt_name = self.prompts_list[selected_index[0]]['name']

        pre_appended_info = ""
        all_prompt_data = self.load_from_file("prompt_customer_info.json", default={})
        selected_customers = all_prompt_data.get(selected_prompt_name, {})

        for customer_name, selected in selected_customers.items():
            if selected:
                customer = next((cust for cust in self.customer_info_list if cust['name'] == customer_name), None)
                if customer:
                    pre_appended_info += f"{customer_name}: {customer['details']}\n"

        combined_prompt = pre_appended_info + "\n" + selected_prompt
        self.log_prompt(combined_prompt)

        response_text = self.submit_prompt_to_chatgpt(combined_prompt)
        if response_text:
            self.import_chatgpt_response(response_text)

    def submit_prompt_to_chatgpt(self, prompt):
        try:
            credentials_path = os.path.expanduser("~/.chatgpt_credentials")
            if not os.path.exists(credentials_path):
                messagebox.showwarning("Warning", "No ChatGPT API key found. Please save the API key first.")
                return

            with open(credentials_path, "r") as file:
                chatgpt_api_key = file.read().strip()

            openai.api_key = chatgpt_api_key

            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system",
                     "content": "You are a specialist in social media, comedy, and storytelling. Your task is to generate a JSON array of objects, each containing a 'caption' field and a 'content' field. Output the response in JSON format only without any additional text or explanations."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800
            )

            response_text = response['choices'][0]['message']['content'].strip()
            logging.info(f"ChatGPT response: {response_text}")

            # Debug print statement
            print(f"ChatGPT response: {response_text}")

            # Validate and sanitize JSON response
            response_text = self.sanitize_json(response_text)
            if not self.is_valid_json(response_text):
                raise json.JSONDecodeError("Response is not in valid JSON format", response_text, 0)

            return response_text
        except openai.error.RateLimitError:
            logging.error("Rate limit exceeded. Please try again later.")
            messagebox.showerror("API Error", "Rate limit exceeded. Please try again later.")
            return None
        except openai.error.AuthenticationError:
            logging.error("Authentication failed. Please check your API key.")
            messagebox.showerror("API Error", "Authentication failed. Please check your API key.")
            return None
        except openai.error.APIConnectionError:
            logging.error("Failed to connect to the API. Please check your network connection.")
            messagebox.showerror("API Error", "Failed to connect to the API. Please check your network connection.")
            return None
        except openai.error.OpenAIError as e:
            logging.error(f"An error occurred: {e}")
            messagebox.showerror("API Error", f"An error occurred: {e}")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")
            return None

    def log_prompt(self, prompt, filename="chatgpt_prompts.log"):
        with open(filename, "a", encoding="utf-8") as log_file:
            log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - PROMPT: {prompt}\n")

    def import_chatgpt_response(self, response):
        logging.info(f"Importing ChatGPT response: {response}")
        self.generated_response = response
        self.parse_chatgpt_response(response)

    def parse_chatgpt_response(self, response):
        try:
            # Attempt to sanitize the JSON response
            response = self.sanitize_json(response)

            # Load the response as JSON
            posts = json.loads(response)
            logging.info(f"Parsed posts: {posts}")

            # Validate the response structure
            if not isinstance(posts, list):
                raise ValueError("The response is not a valid JSON array.")

            for post in posts:
                # Ensure each post is a dictionary and contains the 'caption' and 'content' fields
                if isinstance(post, dict) and 'caption' in post and 'content' in post:
                    self.unpublished_posts.append({
                        "title": post.get("title", "Untitled Post"),
                        "description": post["content"],  # Use 'content' for description
                        "type": post.get("type", "Unknown Type"),
                        "caption": post["caption"],
                        "s3_bucket_url": "",
                        "s3_folder_path": "",
                        "s3_file_name": "",
                        "ready_to_publish": False
                    })
                else:
                    logging.warning(f"Invalid post format: {post}")
                    messagebox.showwarning("Warning", f"Invalid post format: {post}")

            # Save the updated unpublished posts
            self.save_to_file(self.unpublished_posts, "unpublished_posts.json")
            logging.info("ChatGPT response parsed and added to Unpublished Posts.")
            messagebox.showinfo("Success", "ChatGPT response parsed and added to Unpublished Posts.")
        except json.JSONDecodeError as e:
            logging.error(f"JSONDecodeError: {e}")
            messagebox.showerror("Error", f"Failed to parse ChatGPT response as JSON: {e}")
        except Exception as e:
            logging.error(f"Error: {e}")
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")

    def sanitize_json(self, json_string):
        if json_string.startswith("```json"):
            json_string = json_string[7:].strip()  # Remove the ```json prefix
        if json_string.endswith("```"):
            json_string = json_string[:-3].strip()  # Remove the ``` suffix

        # Ensure the JSON string ends correctly
        try:
            json_data = json.loads(json_string)
            if isinstance(json_data, list):
                return json_string
            else:
                raise ValueError("Expected a list of JSON objects.")
        except ValueError:
            return f"[{json_string}]"

    def is_valid_json(self, json_string):
        try:
            json.loads(json_string)
            return True
        except ValueError:
            return False

    def load_and_display_logs(self):
        logs = self.load_logged_prompts()
        self.logs_text.delete("1.0", tk.END)
        self.logs_text.insert(tk.END, "".join(logs))

    def load_logged_prompts(self, filename="chatgpt_prompts.log"):
        if not os.path.exists(filename):
            messagebox.showwarning("Warning", "No log file found.")
            return []

        with open(filename, "r") as log_file:
            return log_file.readlines()

    def load_tags_dropdown(self, dropdown):
        tags = self.load_from_file("tags.json", default=[])
        logging.info(f"Loaded tags: {tags}")
        if isinstance(tags, list) and all(isinstance(tag, dict) and 'name' in tag for tag in tags):
            dropdown['values'] = [tag['name'] for tag in tags]
        else:
            logging.error(f"Tags are not in the expected format: {tags}")
            messagebox.showerror("Error", "Failed to load tags. Tags are not in the expected format.")

    def load_unpublished_posts(self):
        return self.load_from_file("unpublished_posts.json")

    def load_published_posts(self):
        return self.load_from_file("published_posts.json")

    def save_unpublished_post(self):
        post_title = self.unpublished_title.get().strip()
        logging.info(f"Attempting to save post with title: '{post_title}'")

        post = {
            "title": post_title,
            "description": self.unpublished_description.get("1.0", tk.END).strip(),
            "type": self.unpublished_type.get().strip(),
            "caption": self.unpublished_caption.get("1.0", tk.END).strip(),
            "s3_bucket_url": self.s3_bucket_url.get().strip(),
            "s3_folder_path": self.s3_folder_path.get().strip(),
            "s3_file_name": self.s3_file_name.get().strip(),
            "tag": self.unpublished_tags_dropdown.get().strip() or "Uncategorised",  # Default to "Uncategorised"
            "ready_to_publish": self.ready_to_publish_var.get()
        }

        try:
            if self.current_unpublished_index < len(self.unpublished_posts):
                self.unpublished_posts[self.current_unpublished_index] = post
            else:
                self.unpublished_posts.append(post)

            logging.info(f"Updated unpublished posts: {self.unpublished_posts}")
            self.save_to_file(self.unpublished_posts, "unpublished_posts.json")
            messagebox.showinfo("Success", "Post saved successfully.")
        except Exception as e:
            logging.error(f"Error saving post: {e}")
            messagebox.showerror("Error", f"Failed to save post: {e}")
        finally:
            self.refresh_unpublished_posts()

    def display_unpublished_post(self, post):
        self.unpublished_title.delete(0, tk.END)
        self.unpublished_title.insert(0, post['title'])

        self.unpublished_description.delete("1.0", tk.END)
        self.unpublished_description.insert(tk.END, post['description'])

        self.unpublished_type.delete(0, tk.END)
        self.unpublished_type.insert(0, post['type'])

        self.unpublished_caption.delete("1.0", tk.END)
        self.unpublished_caption.insert(tk.END, post['caption'])

        self.s3_bucket_url.delete(0, tk.END)
        self.s3_bucket_url.insert(0, post.get('s3_bucket_url', ''))

        self.s3_folder_path.delete(0, tk.END)
        self.s3_folder_path.insert(0, post.get('s3_folder_path', ''))

        self.s3_file_name.config(state='normal')
        self.s3_file_name.delete(0, tk.END)
        self.s3_file_name.insert(0, post.get('s3_file_name', ''))
        self.s3_file_name.config(state='disabled')

        # Ensure the tag is displayed as "Uncategorised" if it's missing or empty
        tag = post.get('tag', '').strip() or "Uncategorised"
        self.tag_label.config(text=f"Tag: {tag}")

        self.ready_to_publish_var.set(post.get('ready_to_publish', False))
        self.current_unpublished_index = self.unpublished_posts.index(post)

    def refresh_unpublished_posts(self):
        logging.info("Refreshing unpublished posts...")
        self.unpublished_posts = self.load_unpublished_posts()
        logging.info(f"Loaded unpublished posts: {self.unpublished_posts}")
        if self.unpublished_posts:
            self.current_unpublished_index = 0
            self.display_unpublished_post(self.unpublished_posts[0])
        else:
            self.clear_unpublished_post_display()

    def delete_unpublished_post(self):
        post_title = self.unpublished_title.get().strip()
        logging.info(f"Attempting to delete post with title: '{post_title}'")

        if self.current_unpublished_index >= len(self.unpublished_posts):
            messagebox.showwarning("Warning", "No post selected to delete.")
            return

        confirm = messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this post?")
        if not confirm:
            return

        try:
            del self.unpublished_posts[self.current_unpublished_index]
            logging.info(f"Remaining unpublished posts: {self.unpublished_posts}")
            self.save_to_file(self.unpublished_posts, "unpublished_posts.json")
            self.refresh_unpublished_posts()
            messagebox.showinfo("Success", "Post deleted successfully.")
        except Exception as e:
            logging.error(f"Error deleting post: {e}")
            messagebox.showerror("Error", f"Failed to delete post: {e}")

    def clear_unpublished_post_display(self):
        logging.info("Clearing unpublished post display...")
        self.unpublished_title.delete(0, tk.END)
        self.unpublished_description.delete("1.0", tk.END)
        self.unpublished_type.delete(0, tk.END)
        self.unpublished_caption.delete("1.0", tk.END)
        self.s3_bucket_url.delete(0, tk.END)
        self.s3_folder_path.delete(0, tk.END)
        self.s3_file_name.config(state='normal')
        self.s3_file_name.delete(0, tk.END)
        self.s3_file_name.config(state='disabled')
        self.ready_to_publish_var.set(False)

    def next_unpublished_post(self):
        if self.current_unpublished_index < len(self.unpublished_posts) - 1:
            self.current_unpublished_index += 1
            self.display_unpublished_post(self.unpublished_posts[self.current_unpublished_index])
        else:
            messagebox.showinfo("End of List", "No more unpublished posts to show.")

    def last_unpublished_post(self):
        if self.current_unpublished_index > 0:
            self.current_unpublished_index -= 1
            self.display_unpublished_post(self.unpublished_posts[self.current_unpublished_index])
        else:
            messagebox.showinfo("Start of List", "No previous unpublished posts to show.")

    def display_published_post(self, post):
        self.published_title.config(state='normal')
        self.published_title.delete(0, tk.END)
        self.published_title.insert(0, post['title'])
        self.published_title.config(state='disabled')

        self.published_description.config(state='normal')
        self.published_description.delete("1.0", tk.END)
        self.published_description.insert(tk.END, post['description'])
        self.published_description.config(state='disabled')

        self.published_type.config(state='normal')
        self.published_type.delete(0, tk.END)
        self.published_type.insert(0, post['type'])
        self.published_type.config(state='disabled')

        self.published_caption.config(state='normal')
        self.published_caption.delete("1.0", tk.END)
        self.published_caption.insert(tk.END, post['caption'])
        self.published_caption.config(state='disabled')

        self.current_published_index = self.published_posts.index(post)

    def delete_published_post(self):
        post_title = self.published_title.get()
        if not post_title or post_title == "Post Title":
            messagebox.showwarning("Warning", "Please select a valid post to delete.")
            return

        self.published_posts = [post for post in self.published_posts if post['title'] != post_title]
        self.save_to_file(self.published_posts, "published_posts.json")
        messagebox.showinfo("Success", "Post deleted successfully.")
        self.refresh_published_posts()

    def refresh_published_posts(self):
        self.published_posts = self.load_published_posts()
        if self.published_posts:
            self.display_published_post(self.published_posts[0])
        else:
            self.clear_published_post_display()

    def clear_published_post_display(self):
        self.published_title.config(state='normal')
        self.published_title.delete(0, tk.END)
        self.published_title.config(state='disabled')

        self.published_description.config(state='normal')
        self.published_description.delete("1.0", tk.END)
        self.published_description.config(state='disabled')

        self.published_type.config(state='normal')
        self.published_type.delete(0, tk.END)
        self.published_type.config(state='disabled')

        self.published_caption.config(state='normal')
        self.published_caption.delete("1.0", tk.END)
        self.published_caption.config(state='disabled')

    def next_published_post(self):
        if self.current_published_index < len(self.published_posts) - 1:
            self.current_published_index += 1
            self.display_published_post(self.published_posts[self.current_published_index])
        else:
            messagebox.showinfo("End of List", "No more published posts to show.")

    def last_published_post(self):
        if self.current_published_index > 0:
            self.current_published_index -= 1
            self.display_published_post(self.published_posts[self.current_published_index])
        else:
            messagebox.showinfo("Start of List", "No previous published posts to show.")

    def upload_media(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg;*.jpeg;*.png")])
        if not file_path:
            return

        bucket_name = self.s3_bucket_url.get().strip()
        folder_path = self.s3_folder_path.get().strip()

        if not bucket_name or not folder_path:
            messagebox.showwarning("Warning", "Please enter a valid S3 bucket URL and folder path.")
            return

        file_name = os.path.basename(file_path)
        if self.check_s3_file_exists(bucket_name, f"{folder_path}/{file_name}"):
            messagebox.showwarning("Warning", "A file with this name already exists in the S3 bucket.")
            return

        unique_file_name = self.generate_unique_filename(file_name)
        full_file_path = f"{folder_path}/{unique_file_name}"

        self.show_loading("Uploading media, please wait...")
        try:
            self.s3_client.upload_file(file_path, bucket_name, full_file_path)
            s3_url = f"https://{bucket_name}.s3.amazonaws.com/{full_file_path}"
            self.s3_file_name.config(state='normal')
            self.s3_file_name.delete(0, tk.END)
            self.s3_file_name.insert(0, s3_url)
            self.s3_file_name.config(state='disabled')
            messagebox.showinfo("Success", "File uploaded successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to upload file: {e}")
        finally:
            self.hide_loading()

    def check_s3_file_exists(self, bucket_name, file_name):
        try:
            self.s3_client.head_object(Bucket=bucket_name, Key=file_name)
            return True
        except self.s3_client.exceptions.ClientError:
            return False

    def generate_unique_filename(self, file_name):
        name, ext = os.path.splitext(file_name)
        unique_name = f"{name}_{int(time.time())}{ext}"
        return unique_name

    def validate_url(self):
        file_path = self.s3_bucket_url.get().strip()
        folder_path = self.s3_folder_path.get().strip()
        full_path = f"{folder_path}/{self.s3_file_name.get()}"

        if self.check_s3_file_exists(self.s3_bucket_url.get(), full_path):
            messagebox.showinfo("File Exists", "The file exists in the S3 bucket.")
        else:
            messagebox.showwarning("File Not Found", "The file does not exist in the S3 bucket.")

    def export_to_csv(self):
        # Prepare the list of posts to export
        posts_to_export = []
        for post in self.unpublished_posts:
            if post.get('ready_to_publish', False):  # Check if 'Ready to Publish' is ticked
                caption = post.get('caption', '').strip()
                s3_url = post.get('s3_file_name', '').strip()

                # Ensure both caption and URL are present
                if caption and s3_url:
                    posts_to_export.append({
                        'caption': caption,
                        's3_url': s3_url
                    })

        if not posts_to_export:
            messagebox.showwarning("Warning", "No posts are ready to export or have valid Caption and URL.")
            return

        # Determine if the CSV file already exists
        file_exists = os.path.isfile('unpublished_posts.csv')

        # Export to CSV
        with open('unpublished_posts.csv', mode='a', newline='') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(['Caption', 'URL'])  # Write header if file doesn't exist

            for post in posts_to_export:
                writer.writerow([post['caption'], post['s3_url']])

        messagebox.showinfo("Success", "Posts exported to 'unpublished_posts.csv'.")

    def bulk_export_published_posts(self):
        if not self.published_posts:
            messagebox.showwarning("Warning", "No published posts to export.")
            return

        with open('published_posts.csv', mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(
                ['Title', 'Description', 'Type', 'Caption', 'S3 Bucket URL', 'S3 Folder Path', 'S3 File Name',
                 'Ready to Publish'])

            for post in self.published_posts:
                writer.writerow([
                    post['title'],
                    post['description'],
                    post['type'],
                    post['caption'],
                    post['s3_bucket_url'],
                    post['s3_folder_path'],
                    post['s3_file_name'],
                    post['ready_to_publish']
                ])

        messagebox.showinfo("Success", "Published posts exported to 'published_posts.csv'.")

    def publish_post(self, post_title):
        post_to_publish = next((post for post in self.unpublished_posts if post['title'] == post_title), None)

        if not post_to_publish:
            messagebox.showerror("Error", "Post not found in the Unpublished section.")
            return

        self.show_loading("Publishing post, please wait...")
        try:
            self.published_posts.append(post_to_publish)
            self.unpublished_posts = [post for post in self.unpublished_posts if post['title'] != post_title]

            self.save_to_file(self.unpublished_posts, "unpublished_posts.json")
            self.save_to_file(self.published_posts, "published_posts.json")

            messagebox.showinfo("Success", "Post published and moved to the Published section.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to publish post: {e}")
        finally:
            self.hide_loading()
            messagebox.showinfo("Confirmation", "The post has been published successfully.")
            self.refresh_unpublished_posts()
            self.refresh_published_posts()

    def save_chatgpt_key(self):
        chatgpt_key = self.chatgpt_key_entry.get().strip()
        if not chatgpt_key:
            messagebox.showwarning("Warning", "Please enter the ChatGPT API key.")
            return
        credentials_path = os.path.expanduser("~/.chatgpt_credentials")
        with open(credentials_path, "w") as file:
            file.write(chatgpt_key)
        messagebox.showinfo("Success", "ChatGPT API key saved successfully.")

    def delete_chatgpt_key(self):
        credentials_path = os.path.expanduser("~/.chatgpt_credentials")
        if os.path.exists(credentials_path):
            os.remove(credentials_path)
            self.chatgpt_key_entry.delete(0, tk.END)
            messagebox.showinfo("Success", "ChatGPT API key deleted successfully.")
        else:
            messagebox.showwarning("Warning", "No ChatGPT API key found to delete.")

    def load_chatgpt_key(self):
        credentials_path = os.path.expanduser("~/.chatgpt_credentials")
        if os.path.exists(credentials_path):
            with open(credentials_path, "r") as file:
                chatgpt_key = file.read().strip()
            self.chatgpt_key_entry.insert(0, chatgpt_key)
        else:
            self.chatgpt_key_entry.delete(0, tk.END)

    def save_aws_credentials(self):
        access_key = self.aws_access_key_entry.get().strip()
        secret_key = self.aws_secret_key_entry.get().strip()
        region = self.aws_region_entry.get().strip()

        if not access_key or not secret_key or not region:
            messagebox.showwarning("Warning", "Please fill in all AWS credentials fields.")
            return

        if len(access_key) != 20 or len(secret_key) != 40:
            messagebox.showwarning("Warning", "Invalid AWS credentials format.")
            return

        credentials_content = f"""
        [default]
        aws_access_key_id = {access_key}
        aws_secret_access_key = {secret_key}
        region = {region}
        """
        credentials_path = os.path.expanduser("~/.aws/credentials")
        os.makedirs(os.path.dirname(credentials_path), exist_ok=True)
        with open(credentials_path, "w") as file:
            file.write(credentials_content.strip())

        messagebox.showinfo("Success", "AWS credentials saved successfully.")
        self.reload_s3_client()
        self.load_aws_credentials()

    def load_aws_credentials(self):
        credentials_path = os.path.expanduser("~/.aws/credentials")
        try:
            with open(credentials_path, 'r') as file:
                content = file.read()
            access_key = self.extract_credential(content, 'aws_access_key_id')
            secret_key = self.extract_credential(content, 'aws_secret_access_key')
            region = self.extract_credential(content, 'region')

            self.aws_access_key_entry.delete(0, tk.END)
            self.aws_access_key_entry.insert(0, access_key)
            self.aws_secret_key_entry.delete(0, tk.END)
            self.aws_secret_key_entry.insert(0, secret_key)
            self.aws_region_entry.delete(0, tk.END)
            self.aws_region_entry.insert(0, region)
        except FileNotFoundError:
            messagebox.showwarning("Warning", "AWS credentials file not found.")
        except json.JSONDecodeError:
            messagebox.showerror("Error", "Failed to parse AWS credentials file.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load AWS credentials: {e}")

    def extract_credential(self, content, key):
        for line in content.split('\n'):
            if line.startswith(key):
                return line.split('=')[1].strip()
        return ""

    def reload_s3_client(self):
        self.s3_client = boto3.client('s3')

    def load_prompt_info(self, prompt_name):
        all_prompt_data = self.load_from_file("prompt_customer_info.json", default={})
        selected_customers = all_prompt_data.get(prompt_name, {})
        self.set_selected_customers(selected_customers)

    def load_prompt_settings(self):
        settings = self.load_from_file("prompt_settings.json", default={})
        if settings:
            self.prompt_name.delete(0, tk.END)
            self.prompt_name.insert(0, settings.get("prompt_name", ""))
            self.prompt_details.delete("1.0", tk.END)
            self.prompt_details.insert(tk.END, settings.get("prompt_details", ""))
            messagebox.showinfo("Success", "Prompt settings loaded successfully.")
        else:
            messagebox.showwarning("Warning", "No prompt settings found to load.")

    def save_prompt_settings(self):
        settings = {
            "prompt_name": self.prompt_name.get(),
            "prompt_details": self.prompt_details.get("1.0", tk.END).strip()
        }
        self.save_to_file(settings, "prompt_settings.json")
        messagebox.showinfo("Success", "Prompt settings saved successfully.")

    def save_to_file(self, data, file_path):
        try:
            with open(file_path, 'w') as file:
                json.dump(data, file, indent=4)
            logging.info(f"Data successfully saved to {file_path}")
        except IOError as e:
            logging.error(f"Error saving file {file_path}: {e}")
            messagebox.showerror("Error", f"Failed to save data to {file_path}: {e}")

    def load_from_file(self, file_path, default=None):
        if default is None:
            default = []
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as file:
                    data = json.load(file)
                    if isinstance(data, type(default)):
                        logging.info(f"Data successfully loaded from {file_path}")
                        return data
                    else:
                        logging.error(f"Expected {type(default)} from {file_path} but got {type(data)}")
                        return default
            except (json.JSONDecodeError, IOError) as e:
                logging.error(f"Error loading file {file_path}: {e}")
                messagebox.showerror("Error", f"Failed to load data from {file_path}: {e}")
        logging.warning(f"{file_path} does not exist. Returning default value.")
        return default

    def load_customer_info_from_file(self):
        self.customer_info_list = self.load_from_file("customer_info.json")
        self.update_customer_detail_vars()

    def update_customer_detail_vars(self):
        for widget in self.customer_details_frame.winfo_children():
            widget.destroy()

        self.customer_detail_vars = {}
        for customer in self.customer_info_list:
            var = tk.BooleanVar()
            chk = tk.Checkbutton(self.customer_details_frame, text=customer['name'], variable=var)
            chk.pack(anchor='w')
            self.customer_detail_vars[customer['name']] = var

    def clear_customer_checkboxes(self):
        for var in self.customer_detail_vars.values():
            var.set(False)

    def set_selected_customers(self, selected_customers):
        """Sets the state of customer checkboxes based on the provided dictionary."""
        for customer_name, var in self.customer_detail_vars.items():
            var.set(selected_customers.get(customer_name, False))

    def get_selected_customers(self):
        """Gets the state of customer checkboxes and returns them as a dictionary."""
        return {name: var.get() for name, var in self.customer_detail_vars.items()}



    def search_customer_info(self):
        search_name = self.customer_info_name.get().strip()
        if not search_name or search_name == "Customer Information Name":
            messagebox.showwarning("Warning", "Please enter a valid customer name to search.")
            return

        results = [customer['name'] for customer in self.customer_info_list if
                   search_name.lower() in customer['name'].lower()]
        if results:
            self.customer_search_results['values'] = results
            self.customer_search_results.set("Select a result")
        else:
            messagebox.showinfo("No Results", "No customer information found for the given name.")
            self.customer_search_results['values'] = []
            self.customer_search_results.set("")

        # Add filters or tags if necessary
        self.customer_search_results.bind("<KeyRelease>", self.update_customer_search)

    def update_customer_search(self, event):
        search_text = self.customer_search_results.get()
        filtered_results = [customer['name'] for customer in self.customer_info_list if
                            search_text.lower() in customer['name'].lower()]
        self.customer_search_results['values'] = filtered_results

    def create_customer_info(self):
        customer_name = self.customer_info_name.get()
        customer_details = self.customer_info_details.get("1.0", tk.END).strip()

        if customer_name == "Customer Information Name" or not customer_details:
            messagebox.showwarning("Warning", "Please enter both customer name and details.")
            return

        new_customer = {
            "name": customer_name,
            "details": customer_details
        }

        try:
            self.customer_info_list.append(new_customer)
            self.save_to_file(self.customer_info_list, "customer_info.json")
            self.update_customer_detail_vars()
            messagebox.showinfo("Success", "Customer information created successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create customer information: {e}")

        self.customer_info_name.delete(0, tk.END)
        self.customer_info_details.delete("1.0", tk.END)
        self.customer_info_name.insert(0, "Customer Information Name")
        messagebox.showinfo("Confirmation", "The customer information has been created successfully.")

    def read_customer_info(self):
        selected_name = self.customer_search_results.get().strip()
        if not selected_name or selected_name == "Select a result":
            messagebox.showwarning("Warning", "Please select a valid customer from the dropdown list.")
            return

        customer = next((customer for customer in self.customer_info_list if customer['name'] == selected_name), None)
        if customer:
            self.customer_info_details.delete("1.0", tk.END)
            self.customer_info_details.insert(tk.END, customer['details'])
        else:
            messagebox.showinfo("No Results", "No customer information found for the selected name.")

    def update_customer_info(self):
        selected_name = self.customer_search_results.get().strip()
        if not selected_name or selected_name == "Select a result":
            messagebox.showwarning("Warning", "Please select a valid customer from the dropdown list.")
            return

        new_details = self.customer_info_details.get("1.0", tk.END).strip()
        if not new_details:
            messagebox.showwarning("Warning", "Please enter the new details for the customer.")
            return

        for customer in self.customer_info_list:
            if customer['name'] == selected_name:
                customer['details'] = new_details
                break
        else:
            messagebox.showinfo("No Results", "No customer information found for the selected name.")

        self.save_to_file(self.customer_info_list, "customer_info.json")
        self.update_customer_detail_vars()
        messagebox.showinfo("Success", "Customer information updated successfully.")

        # Save the selected customer information
        self.save_selected_customer_info()

    def delete_customer_info(self):
        selected_name = self.customer_search_results.get().strip()
        if not selected_name or selected_name == "Select a result":
            messagebox.showwarning("Warning", "Please select a valid customer from the dropdown list.")
            return

        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the customer information for '{selected_name}'?")
        if not confirm:
            return

        self.customer_info_list = [customer for customer in self.customer_info_list if customer['name'] != selected_name]

        self.save_to_file(self.customer_info_list, "customer_info.json")
        self.update_customer_detail_vars()
        messagebox.showinfo("Success", "Customer information deleted successfully.")

        self.customer_info_name.delete(0, tk.END)
        self.customer_info_details.delete("1.0", tk.END)
        self.customer_search_results.set("")

    def save_prompt_info(self, prompt_name):
        selected_customers = self.get_selected_customers()
        all_prompt_data = self.load_from_file("prompt_customer_info.json", default={})
        if not isinstance(all_prompt_data, dict):
            logging.error(f"Expected dictionary from prompt_customer_info.json but got {type(all_prompt_data)}")
            messagebox.showerror("Error", "Invalid format in prompt_customer_info.json")
            return
        all_prompt_data[prompt_name] = selected_customers
        self.save_to_file(all_prompt_data, "prompt_customer_info.json")
        messagebox.showinfo("Success", f"Customer information for '{prompt_name}' saved successfully.")

    def read_prompt_info(self):
        selected_name = self.prompt_search_results.get().strip()
        if not selected_name or selected_name == "Select a result":
            messagebox.showwarning("Warning", "Please select a valid prompt from the dropdown list.")
            return

        prompt = next((prompt for prompt in self.prompts_list if prompt['name'] == selected_name), None)
        if prompt:
            self.prompt_details.delete("1.0", tk.END)
            self.prompt_details.insert(tk.END, prompt['details'])

            self.clear_customer_checkboxes()
            self.load_prompt_info(selected_name)  # Load customer checkboxes
        else:
            messagebox.showinfo("No Results", "No prompt information found for the selected name.")

    def search_prompt_info(self):
        search_name = self.prompt_name.get().strip()
        if not search_name or search_name == "Prompt Name":
            messagebox.showwarning("Warning", "Please enter a valid prompt name to search.")
            return

        results = [prompt['name'] for prompt in self.prompts_list if search_name.lower() in prompt['name'].lower()]
        if results:
            self.prompt_search_results['values'] = results
            self.prompt_search_results.set("Select a result")
        else:
            messagebox.showinfo("No Results", "No prompt information found for the given name.")
            self.prompt_search_results['values'] = []
            self.prompt_search_results.set("")

    def create_prompt_info(self):
        prompt_name = self.prompt_name.get()
        prompt_details = self.prompt_details.get("1.0", tk.END).strip()

        if prompt_name == "Prompt Name" or not prompt_details:
            messagebox.showwarning("Warning", "Please enter both prompt name and details.")
            return

        new_prompt = {
            "name": prompt_name,
            "details": prompt_details
        }

        try:
            self.prompts_list.append(new_prompt)
            self.save_to_file(self.prompts_list, "prompts.json")
            self.load_prompt_titles()  # Refresh the list of prompts
            messagebox.showinfo("Success", "Prompt information created successfully.")
        except Exception as e:
            logging.error(f"Failed to create prompt information: {e}")
            messagebox.showerror("Error", f"Failed to create prompt information: {e}")

        self.prompt_name.delete(0, tk.END)
        self.prompt_details.delete("1.0", tk.END)
        self.prompt_name.insert(0, "Prompt Name")

    def update_prompt_info(self):
        selected_name = self.prompt_search_results.get().strip()
        if not selected_name or selected_name == "Select a result":
            messagebox.showwarning("Warning", "Please select a valid prompt from the dropdown list.")
            return

        new_details = self.prompt_details.get("1.0", tk.END).strip()
        if not new_details:
            messagebox.showwarning("Warning", "Please enter the new details for the prompt.")
            return

        for prompt in self.prompts_list:
            if prompt['name'] == selected_name:
                prompt['details'] = new_details
                prompt['selected_customers'] = self.get_selected_customers()
                self.save_prompt_info(selected_name)  # Save customer checkboxes
                break
        else:
            messagebox.showinfo("No Results", "No prompt information found for the selected name.")

        self.save_to_file(self.prompts_list, "prompts.json")
        messagebox.showinfo("Success", "Prompt information updated successfully.")

    def delete_prompt_info(self):
        selected_name = self.prompt_search_results.get().strip()
        if not selected_name or selected_name == "Select a result":
            messagebox.showwarning("Warning", "Please select a valid prompt from the dropdown list.")
            return

        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the prompt information for '{selected_name}'?")
        if not confirm:
            return

        self.prompts_list = [prompt for prompt in self.prompts_list if prompt['name'] != selected_name]

        self.save_to_file(self.prompts_list, "prompts.json")
        messagebox.showinfo("Success", "Prompt information deleted successfully.")

        self.prompt_name.delete(0, tk.END)
        self.prompt_details.delete("1.0", tk.END)
        self.prompt_search_results.set("")

    def save_selected_customer_info(self):
        selected_customers = {name: var.get() for name, var in self.customer_detail_vars.items()}
        logging.info(f"Saving selected customer info: {selected_customers}")
        with open("selected_customer_info.json", "w") as file:
            json.dump(selected_customers, file)
        messagebox.showinfo("Success", "Selected customer information saved successfully.")

    def load_selected_customer_info(self):
        if os.path.exists("selected_customer_info.json"):
            try:
                with open("selected_customer_info.json", "r") as file:
                    selected_customers = json.load(file)
                    logging.info(f"Loading selected customer info: {selected_customers}")
                    for name, is_selected in selected_customers.items():
                        if name in self.customer_detail_vars:
                            self.customer_detail_vars[name].set(is_selected)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load selected customer information: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
